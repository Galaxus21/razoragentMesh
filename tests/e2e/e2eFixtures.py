"""Shared E2E Test Fixtures, Oracles, and State Machines for RazorAgent Mesh.

Provides opaque-box test infrastructure for Tiers 1-4.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import math
import random
import re
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
from pydantic import BaseModel, ConfigDict, Field

from razoragentMesh.packages.mandateEngine.crypto.cryptoKeyUtils import (
    extractPublicKeyFromDid,
    formatDid,
    generateKeyPair,
)
from razoragentMesh.packages.mandateEngine.crypto.ed25519Signer import Ed25519Signer
from razoragentMesh.packages.mandateEngine.crypto.ed25519Verifier import Ed25519Verifier
from razoragentMesh.packages.mandateEngine.crypto.jcsCanonicalizer import (
    canonicalizeAndHash,
    canonicalizeJson,
    computeSha256Digest,
)
from razoragentMesh.packages.mandateEngine.mandates.cartMandateSchema import (
    CartItemSchema,
    CartMandate,
    TaxBreakdownSchema,
)
from razoragentMesh.packages.mandateEngine.mandates.executionMandateSchema import ExecutionMandate
from razoragentMesh.packages.mandateEngine.mandates.intentMandateSchema import IntentMandate
from razoragentMesh.packages.mandateEngine.mandates.amendmentMandateSchema import AmendmentMandate
from razoragentMesh.packages.mandateEngine.mandates.mandateFactory import (
    computeMandateHash,
    createSignedAmendmentMandate,
    createSignedCartMandate,
    createSignedExecutionMandate,
    createSignedIntentMandate,
    verifyMandateChain,
    verifyMandateHashChain,
)
from razoragentMesh.packages.mandateEngine.tax.gstrInvoiceEngine import (
    GstrInvoicePayload,
    GstrLineItem,
    generateGstrInvoice,
    isPlaceOfSupplyIntraState,
)
from razoragentMesh.packages.mandateEngine.tax.stateCodeMapping import (
    deriveStateCodeFromPincode,
    pinPrefixToStateCode,
)
from razoragentMesh.packages.mandateEngine.verification.arithmeticEnclave import (
    computeCartSettlementTotal,
    computeGstBreakdown,
    computeLineItemTotal,
    computeTcsWithholding,
    validateIntegerPaise,
)
from razoragentMesh.packages.mandateEngine.settlement.settlementExceptions import (
    ArithmeticDriftException,
    BudgetExceededViolation,
    InvalidPincodeException,
    MandateEngineException,
    MandateHashChainMismatchException,
    NonceReplayException,
    SettlementCompensationTriggeredException,
    SignatureVerificationFailedException,
)
from razoragentMesh.packages.merchantApi.src.constants.hsnCodeDirectory import (
    defaultGstRatePercent,
    hsnCodeDirectory,
    resolveGstRate,
)
from razoragentMesh.tests.mockInfraHelpers import (
    MockQdrantClient,
    MockRazorpayRouteClient,
    MockRedisAsync,
)

# -----------------------------------------------------------------------------
# F01-F04: Arithmetic, Tax, Splitting & Commission Oracles
# -----------------------------------------------------------------------------

def split_bill_conserved(total_amount_paise: int, participant_ratios: List[int]) -> List[int]:
    """Conserved multi-party bill splitting using the Largest Remainder Method (Hamilton method).
    
    Guarantees sum(shares) == total_amount_paise exactly down to 1 paise.
    """
    validateIntegerPaise(total_amount_paise, "total_amount_paise")
    if total_amount_paise < 0:
        raise ArithmeticDriftException("Total bill amount cannot be negative")
    if not participant_ratios:
        return []
    for r in participant_ratios:
        validateIntegerPaise(r, "ratio")
        if r < 0:
            raise ArithmeticDriftException("Participant ratio must be non-negative")
    
    total_ratio = sum(participant_ratios)
    if total_ratio == 0:
        if total_amount_paise == 0:
            return [0] * len(participant_ratios)
        raise ArithmeticDriftException("Total ratio cannot be zero for non-zero bill")
    
    # 1. Base allocation (floor division)
    base_shares = [(total_amount_paise * r) // total_ratio for r in participant_ratios]
    allocated = sum(base_shares)
    remainder = total_amount_paise - allocated
    
    # 2. Fractional parts calculation: (total_amount_paise * r) % total_ratio
    fractional_parts = [
        ((total_amount_paise * r) % total_ratio, idx)
        for idx, r in enumerate(participant_ratios)
    ]
    # Sort descending by remainder, then ascending by index for determinism
    fractional_parts.sort(key=lambda item: (-item[0], item[1]))
    
    # 3. Distribute remaining 1-paise increments to highest remainders
    shares = list(base_shares)
    for i in range(remainder):
        target_idx = fractional_parts[i][1]
        shares[target_idx] += 1
        
    assert sum(shares) == total_amount_paise, "Conservation invariant violated!"
    return shares


@dataclass(frozen=True)
class RouteSplitResult:
    """Conserved fee and commission split result."""
    order_paise: int
    commission_bps: int
    commission_paise: int
    flat_fee_paise: int
    total_fee_paise: int
    merchant_net_paise: int


def calculate_route_splits(
    order_paise: int,
    commission_bps: int,
    flat_fee_paise: int = 0,
) -> RouteSplitResult:
    """Calculates platform commission (bps) and flat fee with strict zero drift and non-negativity."""
    order = validateIntegerPaise(order_paise, "order_paise")
    bps = validateIntegerPaise(commission_bps, "commission_bps")
    flat = validateIntegerPaise(flat_fee_paise, "flat_fee_paise")
    
    if order < 0 or bps < 0 or flat < 0:
        raise ArithmeticDriftException("Order amount, bps, and flat fee must be non-negative")
    if bps > 10000:
        raise ArithmeticDriftException("Commission basis points cannot exceed 10000 (100%)")
        
    comm_paise = (order * bps) // 10000
    total_fee = comm_paise + flat
    if total_fee > order:
        # Clamping or error based on protocol policy
        merchant_net = 0
        total_fee = order
    else:
        merchant_net = order - total_fee
        
    return RouteSplitResult(
        order_paise=order,
        commission_bps=bps,
        commission_paise=comm_paise,
        flat_fee_paise=flat,
        total_fee_paise=total_fee,
        merchant_net_paise=merchant_net,
    )

# -----------------------------------------------------------------------------
# F05-F08: Error Taxonomy, Backoff/Jitter & Durable DLQ
# -----------------------------------------------------------------------------

class ErrorCategory(str, Enum):
    """Classification taxonomy for system and network errors."""
    TRANSIENT_NETWORK = "TRANSIENT_NETWORK"   # e.g., HTTP 504, 503, connect timeout
    TRANSIENT_RATE_LIMIT = "TRANSIENT_RATE_LIMIT" # e.g., HTTP 429
    FATAL_CLIENT = "FATAL_CLIENT"             # e.g., HTTP 400, 404
    FATAL_SCHEMA = "FATAL_SCHEMA"             # e.g., Pydantic validation error
    FATAL_SECURITY = "FATAL_SECURITY"         # e.g., signature mismatch, budget breach
    POISON_PILL = "POISON_PILL"               # Unparseable, corrupted or crashing payload


def classify_error(err: Any) -> ErrorCategory:
    """Classifies an exception, HTTP status code, or message into taxonomy."""
    if isinstance(err, int):
        if err in (429,):
            return ErrorCategory.TRANSIENT_RATE_LIMIT
        if err in (502, 503, 504):
            return ErrorCategory.TRANSIENT_NETWORK
        if err in (400, 404, 405, 422):
            return ErrorCategory.FATAL_CLIENT
        if err in (401, 403):
            return ErrorCategory.FATAL_SECURITY
        return ErrorCategory.TRANSIENT_NETWORK if err >= 500 else ErrorCategory.FATAL_CLIENT
        
    err_str = str(err).lower()
    if "rate limit" in err_str or "429" in err_str or "too many requests" in err_str:
        return ErrorCategory.TRANSIENT_RATE_LIMIT
    if any(k in err_str for k in ("timeout", "timed out", "504", "503", "connection reset", "econnreset")):
        return ErrorCategory.TRANSIENT_NETWORK
    if any(k in err_str for k in ("signature", "unauthorized", "budget", "forbidden", "tamper", "replay")):
        return ErrorCategory.FATAL_SECURITY
    if any(k in err_str for k in ("validation", "pydantic", "schema", "invalid gstin", "invalid pan")):
        return ErrorCategory.FATAL_SCHEMA
    if any(k in err_str for k in ("poison", "malformed", "corrupt", "unhandled json")):
        return ErrorCategory.POISON_PILL
    if isinstance(err, (ArithmeticDriftException, BudgetExceededViolation, SignatureVerificationFailedException, NonceReplayException)):
        return ErrorCategory.FATAL_SECURITY
    return ErrorCategory.FATAL_CLIENT


def is_retryable(category: ErrorCategory) -> bool:
    """Returns True if error category is safe to retry."""
    return category in (ErrorCategory.TRANSIENT_NETWORK, ErrorCategory.TRANSIENT_RATE_LIMIT)


def compute_backoff_delay(
    attempt: int,
    base_delay: float = 0.5,
    max_delay: float = 30.0,
    seed: Optional[int] = None,
) -> float:
    """Computes Full Jitter exponential backoff delay: uniform(0, min(max_delay, base_delay * 2^attempt))."""
    if attempt < 0:
        attempt = 0
    # Prevent extreme 2^attempt float overflow
    bounded_attempt = min(attempt, 30)
    ceiling = min(max_delay, base_delay * (2.0 ** bounded_attempt))
    if ceiling <= 0:
        return 0.0
    rng = random.Random(seed) if seed is not None else random
    return rng.uniform(0.0, ceiling)


class DlqEntryStatus(str, Enum):
    PENDING = "PENDING"
    REPLAYED = "REPLAYED"
    FAILED = "FAILED"
    ABANDONED = "ABANDONED"


class DlqRecord(BaseModel):
    """Durable record schema stored in the Dead Letter Queue."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    
    entryId: str
    idempotencyKey: str
    payload: Dict[str, Any]
    errorMessage: str
    errorCategory: ErrorCategory
    retryCount: int = 0
    maxRetries: int = 5
    status: DlqEntryStatus = DlqEntryStatus.PENDING
    createdAt: int
    lastAttemptAt: Optional[int] = None
    resolvedAt: Optional[int] = None


class DurableDeadLetterQueue:
    """In-memory WAL/Redis-backed durable dead letter queue with idempotency and replay engine."""
    
    def __init__(self, redis_client: Optional[MockRedisAsync] = None) -> None:
        self.redis = redis_client or MockRedisAsync()
        self.store: Dict[str, DlqRecord] = {}
        self.idempotency_index: Dict[str, str] = {}
        self.replayed_keys: set[str] = set()

    async def enqueue(
        self,
        payload: Dict[str, Any],
        error: Exception | str,
        category: Optional[ErrorCategory] = None,
        idempotency_key: Optional[str] = None,
        max_retries: int = 5,
    ) -> str:
        """Persists a failed transaction or poison pill into durable DLQ."""
        if not payload:
            raise ValueError("DLQ payload cannot be empty")
        
        cat = category or classify_error(error)
        err_msg = str(error)
        now = int(time.time())
        idem_key = idempotency_key or hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        
        if idem_key in self.idempotency_index:
            existing_id = self.idempotency_index[idem_key]
            return existing_id
            
        entry_id = f"dlq_{len(self.store) + 1}_{int(time.time() * 1000)}"
        record = DlqRecord(
            entryId=entry_id,
            idempotencyKey=idem_key,
            payload=payload,
            errorMessage=err_msg,
            errorCategory=cat,
            retryCount=0,
            maxRetries=max_retries,
            status=DlqEntryStatus.PENDING,
            createdAt=now,
        )
        self.store[entry_id] = record
        self.idempotency_index[idem_key] = entry_id
        await self.redis.set(f"dlq:entry:{entry_id}", record.model_dump_json())
        return entry_id

    async def peek(self, entry_id: str) -> Optional[DlqRecord]:
        return self.store.get(entry_id)

    async def replay(self, entry_id: str, handler_fn: Callable[[Dict[str, Any]], Any]) -> Tuple[bool, Any]:
        """Idempotently replays a DLQ entry using state fencing and handler execution."""
        record = self.store.get(entry_id)
        if not record:
            raise KeyError(f"DLQ entry {entry_id} not found")
            
        if record.idempotencyKey in self.replayed_keys or record.status == DlqEntryStatus.REPLAYED:
            return True, {"status": "already_replayed", "entryId": entry_id}
            
        now = int(time.time())
        try:
            result = handler_fn(record.payload)
            if hasattr(result, "__await__"):
                result = await result
                
            updated = record.model_copy(update={
                "status": DlqEntryStatus.REPLAYED,
                "retryCount": record.retryCount + 1,
                "lastAttemptAt": now,
                "resolvedAt": now,
            })
            self.store[entry_id] = updated
            self.replayed_keys.add(record.idempotencyKey)
            await self.redis.set(f"dlq:entry:{entry_id}", updated.model_dump_json())
            return True, result
        except Exception as e:
            new_status = DlqEntryStatus.FAILED if (record.retryCount + 1 >= record.maxRetries) else DlqEntryStatus.PENDING
            updated = record.model_copy(update={
                "status": new_status,
                "retryCount": record.retryCount + 1,
                "errorMessage": str(e),
                "lastAttemptAt": now,
            })
            self.store[entry_id] = updated
            await self.redis.set(f"dlq:entry:{entry_id}", updated.model_dump_json())
            return False, {"error": str(e), "status": new_status}

    def list_entries(self, status: Optional[DlqEntryStatus] = None) -> List[DlqRecord]:
        if status is None:
            return list(self.store.values())
        return [r for r in self.store.values() if r.status == status]

# -----------------------------------------------------------------------------
# F09, F10, F12: Statutory GSTIN, PAN, Invoice & State Code Enclaves
# -----------------------------------------------------------------------------

GSTIN_PATTERN = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"
PAN_PATTERN = r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$"

VALID_STATE_CODES = {
    "01", "02", "03", "04", "05", "06", "07", "08", "09", "10",
    "11", "12", "13", "14", "15", "16", "17", "18", "19", "20",
    "21", "22", "23", "24", "25", "26", "27", "28", "29", "30",
    "31", "32", "33", "34", "35", "36", "37", "38", "97", "99",
}


def validate_gstin(gstin: str) -> bool:
    """Validates 15-character Indian GSTIN format, valid state prefix, and checksum structure."""
    if not isinstance(gstin, str) or len(gstin) != 15:
        return False
    if not re.match(GSTIN_PATTERN, gstin):
        return False
    state_prefix = gstin[:2]
    if state_prefix not in VALID_STATE_CODES:
        return False
    return True


def validate_pan(pan: str) -> bool:
    """Validates 10-character Indian Permanent Account Number (PAN)."""
    if not isinstance(pan, str) or len(pan) != 10:
        return False
    return bool(re.match(PAN_PATTERN, pan))


def extract_pan_from_gstin(gstin: str) -> Optional[str]:
    """Extracts 10-character PAN embedded in characters 2..12 of a 15-char GSTIN."""
    if not validate_gstin(gstin):
        return None
    return gstin[2:12]


def extract_state_from_gstin(gstin: str) -> Optional[str]:
    """Extracts 2-digit GST state code from characters 0..2."""
    if not validate_gstin(gstin):
        return None
    return gstin[:2]


class E2eInvoiceLineItem(BaseModel):
    """Rule 46 compliant itemized line."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    
    skuId: str = Field(min_length=1)
    description: str = Field(min_length=1)
    hsnSacCode: str = Field(pattern=r"^[0-9]{4,8}$")
    quantity: int = Field(gt=0)
    unitPricePaise: int = Field(gt=0)
    taxableAmountPaise: int = Field(gt=0)
    gstRatePercent: int = Field(ge=0, le=28)
    cgstPaise: int = Field(ge=0)
    sgstPaise: int = Field(ge=0)
    igstPaise: int = Field(ge=0)
    totalPaise: int = Field(gt=0)


class E2eGstr1Invoice(BaseModel):
    """GSTR-1 Rule 46 Tax Invoice with full statutory assertions."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    
    invoiceNumber: str = Field(min_length=1, max_length=16)
    invoiceDate: str = Field(min_length=10)
    supplierGstin: str = Field(min_length=15, max_length=15)
    supplierStateCode: str = Field(min_length=2, max_length=2)
    recipientGstin: Optional[str] = Field(default=None, min_length=15, max_length=15)
    recipientStateCode: str = Field(min_length=2, max_length=2)
    placeOfSupplyStateCode: str = Field(min_length=2, max_length=2)
    isReverseChargeApplicable: bool = False
    isIntraState: bool
    lineItems: List[E2eInvoiceLineItem] = Field(min_length=1)
    taxableSubtotalPaise: int = Field(gt=0)
    totalCgstPaise: int = Field(ge=0)
    totalSgstPaise: int = Field(ge=0)
    totalIgstPaise: int = Field(ge=0)
    totalTaxPaise: int = Field(ge=0)
    totalTcsPaise: int = Field(ge=0)
    shippingPaise: int = Field(ge=0, default=0)
    discountPaise: int = Field(ge=0, default=0)
    grandTotalPaise: int = Field(gt=0)
    cryptographicAuditHash: str = Field(min_length=64, max_length=64)

# -----------------------------------------------------------------------------
# F14: Two-Phase Commit FSM Engine
# -----------------------------------------------------------------------------

class SagaState(str, Enum):
    INITIAL = "INITIAL"
    PREPARED = "PREPARED"
    COMMITTED = "COMMITTED"
    ABORTED = "ABORTED"


class TwoPhaseCommitFsm:
    """Stateful 2PC Finite State Machine managing PREPARE, COMMIT, and compensating ROLLBACK."""
    
    def __init__(self, route_client: Any) -> None:
        self.route_client = route_client
        self.state: SagaState = SagaState.INITIAL
        self.fencing_token: int = 0
        self.completed_transfers: List[Dict[str, Any]] = []
        self.reversed_transfers: List[Dict[str, Any]] = []

    def prepare(self, fencing_token: int) -> bool:
        if self.state != SagaState.INITIAL:
            raise IllegalStateTransitionError(f"Cannot PREPARE from state {self.state}")
        if fencing_token <= self.fencing_token:
            raise FencingTokenViolationError("Fencing token must be strictly monotonic")
        self.fencing_token = fencing_token
        self.state = SagaState.PREPARED
        return True

    async def commit_transfers(self, transfer_requests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if self.state != SagaState.PREPARED:
            raise IllegalStateTransitionError(f"Cannot COMMIT from state {self.state}")
            
        try:
            for req in transfer_requests:
                # Dispatch transfer
                if hasattr(self.route_client, "createTransfer"):
                    res = await self.route_client.createTransfer(
                        recipientAccountId=req["account"],
                        amountPaise=req["amount"],
                        notes=req.get("notes", {}),
                    )
                else:
                    res = {"id": f"trf_{len(self.completed_transfers)+1}", "amount": req["amount"], "account": req["account"]}
                self.completed_transfers.append(res)
                
            self.state = SagaState.COMMITTED
            return self.completed_transfers
        except Exception as e:
            await self.rollback()
            raise SettlementCompensationTriggeredException(f"2PC Commit failed: {str(e)}") from e

    async def rollback(self) -> None:
        """Executes LIFO compensation for all completed split transfers."""
        self.state = SagaState.ABORTED
        for trf in reversed(self.completed_transfers):
            trf_id = trf.get("id") or trf.get("transferId")
            amt = trf.get("amount") or trf.get("amountPaise")
            if hasattr(self.route_client, "reverseTransfer") and trf_id:
                rev = await self.route_client.reverseTransfer(trf_id, amt)
                self.reversed_transfers.append(rev)
            else:
                self.reversed_transfers.append({"id": f"rev_{trf_id}", "transferId": trf_id, "amount": amt})


class IllegalStateTransitionError(Exception):
    pass

class FencingTokenViolationError(Exception):
    pass

# -----------------------------------------------------------------------------
# Actor Signers & Fixture Generator
# -----------------------------------------------------------------------------

@dataclass
class E2eTestActors:
    user_cfo: Ed25519Signer
    buyer_agent: Ed25519Signer
    merchant_nexus: Ed25519Signer
    attacker_node: Ed25519Signer


def setup_e2e_actors() -> E2eTestActors:
    """Generates standard deterministic actor signers."""
    # Deterministic keys
    user_key = "ec89f8790fa0bc33882dd0c02c67a79a0a68f6976f52010b7e656564db3c9f8a"
    buyer_key = "ad1b82a9cce6d36564c79f026ff7479072875d80cb85b5b95a3478df90572270"
    merchant_key = "ac262c2b5daf3f4272ed052f7b331cbb6152588ae58dfb022f71c7b8a2c45364"
    attacker_key = "6b9f06cfafa2621131b65131d23ef93a3897efc6fe85488b9e7af97f36ce7dde"
    
    return E2eTestActors(
        user_cfo=Ed25519Signer(user_key),
        buyer_agent=Ed25519Signer(buyer_key),
        merchant_nexus=Ed25519Signer(merchant_key),
        attacker_node=Ed25519Signer(attacker_key),
    )
