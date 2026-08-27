"""Comprehensive Unit and Integration Test Suite for Milestone 3 Statutory Compliance.

Covers:
1. Canonical Luhn Mod-36 GSTIN checksum computation and verification in `packages/mandateEngine/tax/gstinValidator.py`.
2. Valid Indian GSTINs with correct Luhn Mod-36 check digits across all 38 states (01-38) and entity types.
3. CartMandate Pydantic @field_validator enforcement, rejecting invalid check digits, invalid lengths, and regex violations.
4. Mandate Factory `createSignedCartMandate` validation and cryptographic signature invariance.
5. FastAPI Settlement Route `/api/v1/settlement/execute` schema ingress validation and zero-side-effect isolation on 422 errors.
6. Cross-state and Place-of-Supply tax breakdown consistency.
7. Parity between `merchantApi` registrar and `mandateEngine` tax validator.
8. Adversarial injection, whitespace fuzzing, and character mutation resistance.
"""

import asyncio
from typing import Any, Dict, List, Optional, Tuple
import fakeredis.aioredis
import httpx
from httpx import ASGITransport
import pytest
from pydantic import ValidationError

try:
    from razoragentMesh.packages.mandateEngine.crypto.cryptoKeyUtils import generateKeyPair
    from razoragentMesh.packages.mandateEngine.crypto.ed25519Signer import Ed25519Signer
    from razoragentMesh.packages.mandateEngine.crypto.ed25519Verifier import Ed25519Verifier
    from razoragentMesh.packages.mandateEngine.crypto.jcsCanonicalizer import canonicalizeJson
    from razoragentMesh.packages.mandateEngine.mandateApp import (
        ExecuteSettlementRequestSchema,
        createMandateApp,
    )
    from razoragentMesh.packages.mandateEngine.mandates.cartMandateSchema import (
        CartItemSchema,
        CartMandate,
        TaxBreakdownSchema,
    )
    from razoragentMesh.packages.mandateEngine.mandates.executionMandateSchema import ExecutionMandate
    from razoragentMesh.packages.mandateEngine.mandates.intentMandateSchema import IntentMandate
    from razoragentMesh.packages.mandateEngine.mandates.mandateFactory import (
        createSignedCartMandate,
        createSignedExecutionMandate,
        createSignedIntentMandate,
    )
    from razoragentMesh.packages.mandateEngine.nonce.nonceLedger import NonceLedger
    from razoragentMesh.packages.mandateEngine.settlement.razorpayRouteClient import RazorpayRouteClient
    from razoragentMesh.packages.mandateEngine.settlement.settlementOrchestrator import SettlementOrchestrator
    from razoragentMesh.packages.mandateEngine.tax.gstinValidator import (
        computeGstinChecksum,
        gstCharsTable,
        gstinLength,
        gstinRegexPattern,
        validateGstin,
    )
    from razoragentMesh.packages.mandateEngine.tax.stateCodeMapping import deriveStateCodeFromPincode
    from razoragentMesh.packages.mandateEngine.telemetryEmitter import TelemetryEventEmitter
    from razoragentMesh.packages.merchantApi.src.onboarding.merchantRegistrar import (
        validateGstin as registrarValidateGstin,
    )
    from razoragentMesh.tests.mockInfraHelpers import MockRedisAsync
except ModuleNotFoundError:
    from packages.mandateEngine.crypto.cryptoKeyUtils import generateKeyPair
    from packages.mandateEngine.crypto.ed25519Signer import Ed25519Signer
    from packages.mandateEngine.crypto.ed25519Verifier import Ed25519Verifier
    from packages.mandateEngine.crypto.jcsCanonicalizer import canonicalizeJson
    from packages.mandateEngine.mandateApp import (
        ExecuteSettlementRequestSchema,
        createMandateApp,
    )
    from packages.mandateEngine.mandates.cartMandateSchema import (
        CartItemSchema,
        CartMandate,
        TaxBreakdownSchema,
    )
    from packages.mandateEngine.mandates.executionMandateSchema import ExecutionMandate
    from packages.mandateEngine.mandates.intentMandateSchema import IntentMandate
    from packages.mandateEngine.mandates.mandateFactory import (
        createSignedCartMandate,
        createSignedExecutionMandate,
        createSignedIntentMandate,
    )
    from packages.mandateEngine.nonce.nonceLedger import NonceLedger
    from packages.mandateEngine.settlement.razorpayRouteClient import RazorpayRouteClient
    from packages.mandateEngine.settlement.settlementOrchestrator import SettlementOrchestrator
    from packages.mandateEngine.tax.gstinValidator import (
        computeGstinChecksum,
        gstCharsTable,
        gstinLength,
        gstinRegexPattern,
        validateGstin,
    )
    from packages.mandateEngine.tax.stateCodeMapping import deriveStateCodeFromPincode
    from packages.mandateEngine.telemetryEmitter import TelemetryEventEmitter
    from packages.merchantApi.src.onboarding.merchantRegistrar import (
        validateGstin as registrarValidateGstin,
    )
    from tests.mockInfraHelpers import MockRedisAsync


# Pre-computed mathematically verified GSTINs for all 38 Indian State Codes (01-38)
VALID_STATE_GSTIN_MAP: Dict[str, str] = {
    "01": "01AABCU9603R1Z1",  # Jammu & Kashmir
    "02": "02AABCU9603R1ZZ",  # Himachal Pradesh
    "03": "03AABCU9603R1ZX",  # Punjab
    "04": "04AABCU9603R1ZV",  # Chandigarh
    "05": "05AABCU9603R1ZT",  # Uttarakhand
    "06": "06AABCU9603R1ZR",  # Haryana
    "07": "07AABCU9603R1ZP",  # Delhi
    "08": "08AABCU9603R1ZN",  # Rajasthan
    "09": "09AABCU9603R1ZL",  # Uttar Pradesh
    "10": "10AABCU9603R1Z2",  # Bihar
    "11": "11AABCU9603R1Z0",  # Sikkim
    "12": "12AABCU9603R1ZY",  # Arunachal Pradesh
    "13": "13AABCU9603R1ZW",  # Nagaland
    "14": "14AABCU9603R1ZU",  # Manipur
    "15": "15AABCU9603R1ZS",  # Mizoram
    "16": "16AABCU9603R1ZQ",  # Tripura
    "17": "17AABCU9603R1ZO",  # Meghalaya
    "18": "18AABCU9603R1ZM",  # Assam
    "19": "19AABCU9603R1ZK",  # West Bengal
    "20": "20AABCU9603R1Z1",  # Jharkhand
    "21": "21AABCU9603R1ZZ",  # Odisha
    "22": "22AABCU9603R1ZX",  # Chhattisgarh
    "23": "23AABCU9603R1ZV",  # Madhya Pradesh
    "24": "24AABCU9603R1ZT",  # Gujarat
    "25": "25AABCU9603R1ZR",  # Daman & Diu (Legacy)
    "26": "26AABCU9603R1ZP",  # Dadra & Nagar Haveli
    "27": "27AABCU9603R1ZN",  # Maharashtra
    "28": "28AABCU9603R1ZL",  # Andhra Pradesh (Legacy)
    "29": "29AABCU9603R1ZJ",  # Karnataka
    "30": "30AABCU9603R1Z0",  # Goa
    "31": "31AABCU9603R1ZY",  # Lakshadweep
    "32": "32AABCU9603R1ZW",  # Kerala
    "33": "33AABCU9603R1ZU",  # Tamil Nadu
    "34": "34AABCU9603R1ZS",  # Puducherry
    "35": "35AABCU9603R1ZQ",  # Andaman & Nicobar Islands
    "36": "36AABCU9603R1ZO",  # Telangana
    "37": "37AABCU9603R1ZM",  # Andhra Pradesh (New)
    "38": "38AABCU9603R1ZK",  # Ladakh
}

VALID_ENTITY_TYPE_GSTINS: Dict[str, str] = {
    "C_Company": "29AABCU9603R1ZJ",
    "P_Individual": "29AABPU9603R1ZS",
    "F_Firm": "29AABFU9603R1ZD",
    "H_HUF": "29AABHU9603R1Z9",
    "A_AOP": "29AABAU9603R1ZN",
    "T_Trust": "29AABTU9603R1ZK",
    "B_BOI": "29AABBU9603R1ZL",
    "L_LocalAuth": "29AABLU9603R1Z0",
    "J_ArtificialJuridical": "29AABJU9603R1Z4",
    "G_Government": "29AABGU9603R1ZB",
}


def _createSignerTriplet() -> Tuple[Ed25519Signer, Ed25519Signer, Ed25519Signer]:
    return (
        Ed25519Signer(generateKeyPair()[0]),
        Ed25519Signer(generateKeyPair()[0]),
        Ed25519Signer(generateKeyPair()[0]),
    )


def _buildStandardCartItem(unitPricePaise: int = 100000, gstRatePercent: int = 18) -> CartItemSchema:
    return CartItemSchema(
        skuId="SKU-CORP-01",
        quantity=1,
        unitPricePaise=unitPricePaise,
        hsnCode="84713010",
        gstRatePercent=gstRatePercent,
        lineTotalPaise=unitPricePaise,
    )


def _buildStandardTaxBreakdown(
    taxableSubtotalPaise: int = 100000,
    isIntraState: bool = True,
    gstRatePercent: int = 18,
) -> TaxBreakdownSchema:
    totalTax = (taxableSubtotalPaise * gstRatePercent) // 100
    if isIntraState:
        halfTax = totalTax // 2
        return TaxBreakdownSchema(
            cgstPaise=halfTax,
            sgstPaise=halfTax,
            igstPaise=0,
            totalTaxPaise=totalTax,
        )
    return TaxBreakdownSchema(
        cgstPaise=0,
        sgstPaise=0,
        igstPaise=totalTax,
        totalTaxPaise=totalTax,
    )


def _buildDirectCartMandate(
    merchantGstin: str,
    merchantStateCode: str = "29",
    buyerDeliveryPincode: str = "560001",
    buyerDeliveryStateCode: str = "29",
    totalPaise: int = 118000,
) -> CartMandate:
    item = _buildStandardCartItem()
    tax = _buildStandardTaxBreakdown(isIntraState=(merchantStateCode == buyerDeliveryStateCode))
    return CartMandate(
        cartId="M-C-DIRECT-001",
        merchantDid="did:agent:" + ("a" * 64),
        merchantGstin=merchantGstin,
        merchantStateCode=merchantStateCode,
        buyerDeliveryPincode=buyerDeliveryPincode,
        buyerDeliveryStateCode=buyerDeliveryStateCode,
        items=[item],
        taxableSubtotalPaise=100000,
        taxBreakdown=tax,
        shippingPaise=0,
        discountPaise=0,
        totalPaise=totalPaise,
        inventoryLockToken="lock_direct_001",
        inventoryLockExpiresAt=2000000000,
        nonce="nonce_direct_001",
        timestamp=1700000000,
        merchantSignature="00" * 64,
    )


def _configureTestFastApp(routeClient: Optional[RazorpayRouteClient] = None) -> Tuple[Any, RazorpayRouteClient, TelemetryEventEmitter]:
    app = createMandateApp()
    fakeRedis = fakeredis.aioredis.FakeRedis()
    nonceLedger = NonceLedger(fakeRedis)
    client = routeClient or RazorpayRouteClient(isMockMode=True)
    orchestrator = SettlementOrchestrator(
        routeClient=client,
        nonceLedger=nonceLedger,
        protocolFeeAccount="acc_protocol_fees",
        protocolFeePaise=50,
    )
    telemetryEmitter = TelemetryEventEmitter()
    app.state.redis = fakeRedis
    app.state.nonceLedger = nonceLedger
    app.state.routeClient = client
    app.state.settlementOrchestrator = orchestrator
    app.state.telemetryEmitter = telemetryEmitter
    return app, client, telemetryEmitter


class TestCanonicalGstinValidatorCore:
    """Unit tests for core functions in packages/mandateEngine/tax/gstinValidator.py."""

    @pytest.mark.parametrize("state_code, valid_gstin", VALID_STATE_GSTIN_MAP.items())
    def testComputeGstinChecksumAll38States(self, state_code: str, valid_gstin: str) -> None:
        """computeGstinChecksum calculates the exact 15th Luhn Mod-36 check character across all 38 states."""
        prefix14 = valid_gstin[:14]
        expectedChecksumChar = valid_gstin[14]
        computedChecksumChar = computeGstinChecksum(prefix14)
        assert computedChecksumChar == expectedChecksumChar
        assert computedChecksumChar in gstCharsTable

    @pytest.mark.parametrize("state_code, valid_gstin", VALID_STATE_GSTIN_MAP.items())
    def testValidateGstinAll38StatesValid(self, state_code: str, valid_gstin: str) -> None:
        """validateGstin returns True for canonical GSTINs of all 38 Indian states."""
        assert validateGstin(valid_gstin) is True

    @pytest.mark.parametrize("entity_label, valid_gstin", VALID_ENTITY_TYPE_GSTINS.items())
    def testValidateGstinEntityTypes(self, entity_label: str, valid_gstin: str) -> None:
        """validateGstin correctly validates all 10 PAN entity types (Company, Individual, Firm, etc.)."""
        assert validateGstin(valid_gstin) is True

    def testValidateGstinChecksumMutationRejection(self) -> None:
        """Flipping the 15th check character to any of the other 35 radix-36 characters must fail."""
        valid_gstin = "29AABCU9603R1ZJ"
        prefix14 = valid_gstin[:14]
        correct_check = valid_gstin[14]

        for char in gstCharsTable:
            if char != correct_check:
                mutated_gstin = prefix14 + char
                assert validateGstin(mutated_gstin) is False, f"Mutation {mutated_gstin} must be rejected"

    def testValidateGstinAdjacentTranspositionRejection(self) -> None:
        """Swapping adjacent characters anywhere in a valid GSTIN must fail checksum validation."""
        valid_gstin = "29AABCU9603R1ZJ"
        for idx in range(len(valid_gstin) - 1):
            chars = list(valid_gstin)
            chars[idx], chars[idx + 1] = chars[idx + 1], chars[idx]
            swapped_gstin = "".join(chars)
            if swapped_gstin != valid_gstin:
                assert validateGstin(swapped_gstin) is False, f"Transposition {swapped_gstin} must fail"

    @pytest.mark.parametrize("invalid_length_gstin", [
        "",
        "29",
        "29AABCU9603",
        "29AABCU9603R1Z",
        "29AABCU9603R1ZJJ",
        "29AABCU9603R1ZJ00000",
    ])
    def testValidateGstinInvalidLengthFails(self, invalid_length_gstin: str) -> None:
        """validateGstin returns False for any string whose length != 15."""
        assert validateGstin(invalid_length_gstin) is False

    @pytest.mark.parametrize("invalid_type", [
        None,
        123456789012345,
        12.345,
        True,
        False,
        ["29AABCU9603R1ZJ"],
        {"gstin": "29AABCU9603R1ZJ"},
    ])
    def testValidateGstinInvalidTypeFails(self, invalid_type: Any) -> None:
        """validateGstin returns False for non-string inputs without throwing unhandled exceptions."""
        assert validateGstin(invalid_type) is False

    @pytest.mark.parametrize("malformed_gstin", [
        "29aabcu9603r1zj",
        "29Aabcu9603R1zJ",
        "29-ABCU9603R1ZJ",
        "29AABCU9603R1Z!",
        "29@ABCU9603R1ZJ",
        "29AABCU9603R 1Z",
        "29AABCU9603R11J",
        "00AABCU9603R1Z1",
        "39AABCU9603R1Z0",
        "99AABCU9603R1Z0",
        "XXAABCU9603R1ZJ",
    ])
    def testValidateGstinMalformedStructureFails(self, malformed_gstin: str) -> None:
        """validateGstin returns False for malformed regex or invalid state codes."""
        assert validateGstin(malformed_gstin) is False


class TestCartMandateSchemaGstinValidation:
    """Unit tests for Pydantic @field_validator("merchantGstin") on CartMandate schema."""

    def testCartMandateNominalValidGstin(self) -> None:
        """CartMandate instantiates cleanly with valid Luhn Mod-36 GSTIN."""
        mandate = _buildDirectCartMandate(merchantGstin="29AABCU9603R1ZJ")
        assert mandate.merchantGstin == "29AABCU9603R1ZJ"
        assert mandate.cartId == "M-C-DIRECT-001"

    def testCartMandateInvalidCheckDigitRaisesValidationError(self) -> None:
        """CartMandate raises pydantic.ValidationError when check digit is incorrect."""
        with pytest.raises(ValidationError) as exc_info:
            _buildDirectCartMandate(merchantGstin="29AABCU9603R1ZM")

        errors = exc_info.value.errors()
        assert len(errors) >= 1
        assert "merchantGstin" in str(errors[0]["loc"])
        assert "Invalid Indian GSTIN: failed format or Luhn Mod-36 checksum verification" in errors[0]["msg"]

    @pytest.mark.parametrize("bad_gstin", [
        "29AABCU9603R1Z5",
        "29AAAAA0000A1Z5",
        "27AAPFU0939F1Z0",
        "07AAAAA0000A1Z0",
    ])
    def testCartMandateWrongCheckDigitRejections(self, bad_gstin: str) -> None:
        """Various wrong check digits consistently raise pydantic.ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            _buildDirectCartMandate(merchantGstin=bad_gstin)
        assert "merchantGstin" in str(exc_info.value.errors()[0]["loc"])

    @pytest.mark.parametrize("bad_length_gstin", [
        "29AABCU9603R1Z",
        "29AABCU9603R1ZJJ",
        "SHORT",
    ])
    def testCartMandateInvalidLengthRaisesValidationError(self, bad_length_gstin: str) -> None:
        """GSTINs not exactly 15 characters raise pydantic.ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            _buildDirectCartMandate(merchantGstin=bad_length_gstin)
        assert "merchantGstin" in str(exc_info.value.errors()[0]["loc"])

    @pytest.mark.parametrize("bad_format_gstin", [
        "29aabcu9603r1zj",
        "29AABCU9603R1Z!",
        "00AABCU9603R1Z1",
        "99AABCU9603R1Z0",
    ])
    def testCartMandateInvalidFormatRaisesValidationError(self, bad_format_gstin: str) -> None:
        """Regex and state code violations raise pydantic.ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            _buildDirectCartMandate(merchantGstin=bad_format_gstin)
        assert "merchantGstin" in str(exc_info.value.errors()[0]["loc"])

    def testCartMandateSerializationRoundtrip(self) -> None:
        """CartMandate JSON serialization and parsing preserves statutory GSTIN invariant."""
        mandate = _buildDirectCartMandate(merchantGstin="27AABCU9603R1ZN", merchantStateCode="27")
        dumped_json = mandate.model_dump_json()
        restored = CartMandate.model_validate_json(dumped_json)
        assert restored.merchantGstin == "27AABCU9603R1ZN"
        assert restored == mandate

    def testCartMandateExtraFieldsForbidden(self) -> None:
        """Passing extraneous fields to CartMandate raises pydantic.ValidationError."""
        item = _buildStandardCartItem()
        tax = _buildStandardTaxBreakdown()
        with pytest.raises(ValidationError):
            CartMandate(
                cartId="M-C-EXTRA",
                merchantDid="did:agent:" + ("b" * 64),
                merchantGstin="29AABCU9603R1ZJ",
                merchantStateCode="29",
                buyerDeliveryPincode="560001",
                buyerDeliveryStateCode="29",
                items=[item],
                taxableSubtotalPaise=100000,
                taxBreakdown=tax,
                totalPaise=118000,
                inventoryLockToken="lock_tok",
                inventoryLockExpiresAt=2000000000,
                nonce="nonce_extra",
                timestamp=1700000000,
                merchantSignature="00" * 64,
                unauthorizedField="injected",
            )


class TestSignedCartMandateFactoryGstinValidation:
    """Tests createSignedCartMandate factory function and cryptographic signature bounds."""

    @pytest.mark.parametrize("state_code, valid_gstin", [
        ("07", "07AABCU9603R1ZP"),
        ("27", "27AABCU9603R1ZN"),
        ("29", "29AABCU9603R1ZJ"),
        ("33", "33AABCU9603R1ZU"),
        ("36", "36AABCU9603R1ZO"),
    ])
    def testCreateSignedCartMandateNominalSuccess(self, state_code: str, valid_gstin: str) -> None:
        """createSignedCartMandate creates valid signed mandate and verified Ed25519 signature."""
        _, merchantSigner, _ = _createSignerTriplet()
        item = _buildStandardCartItem()
        tax = _buildStandardTaxBreakdown()

        signedCart = createSignedCartMandate(
            cartId="M-C-SIGNED-001",
            merchantSigner=merchantSigner,
            merchantGstin=valid_gstin,
            merchantStateCode=state_code,
            buyerDeliveryPincode="560001",
            buyerDeliveryStateCode="29",
            items=[item],
            taxableSubtotalPaise=100000,
            taxBreakdown=tax,
            shippingPaise=0,
            discountPaise=0,
            totalPaise=118000,
            inventoryLockToken="lock_signed_001",
            inventoryLockExpiresAt=2000000000,
        )

        assert isinstance(signedCart, CartMandate)
        assert signedCart.merchantGstin == valid_gstin
        assert len(signedCart.merchantSignature) == 128

        unsignedPayload = {
            "buyerDeliveryPincode": signedCart.buyerDeliveryPincode,
            "buyerDeliveryStateCode": signedCart.buyerDeliveryStateCode,
            "cartId": signedCart.cartId,
            "discountPaise": signedCart.discountPaise,
            "inventoryLockExpiresAt": signedCart.inventoryLockExpiresAt,
            "inventoryLockToken": signedCart.inventoryLockToken,
            "items": [i.model_dump() for i in signedCart.items],
            "merchantDid": signedCart.merchantDid,
            "merchantGstin": signedCart.merchantGstin,
            "merchantStateCode": signedCart.merchantStateCode,
            "nonce": signedCart.nonce,
            "shippingPaise": signedCart.shippingPaise,
            "taxBreakdown": signedCart.taxBreakdown.model_dump(),
            "taxableSubtotalPaise": signedCart.taxableSubtotalPaise,
            "timestamp": signedCart.timestamp,
            "totalPaise": signedCart.totalPaise,
        }
        canonicalBytes = canonicalizeJson(unsignedPayload)
        assert Ed25519Verifier.verifySignature(merchantSigner.getPublicKeyHex(), canonicalBytes, signedCart.merchantSignature) is True

    def testCreateSignedCartMandateInvalidGstinRaisesBeforeSign(self) -> None:
        """createSignedCartMandate raises ValidationError when invalid check digit is provided."""
        _, merchantSigner, _ = _createSignerTriplet()
        item = _buildStandardCartItem()
        tax = _buildStandardTaxBreakdown()

        with pytest.raises(ValidationError) as exc_info:
            createSignedCartMandate(
                cartId="M-C-SIGNED-FAIL",
                merchantSigner=merchantSigner,
                merchantGstin="29AABCU9603R1ZM",
                merchantStateCode="29",
                buyerDeliveryPincode="560001",
                buyerDeliveryStateCode="29",
                items=[item],
                taxableSubtotalPaise=100000,
                taxBreakdown=tax,
                shippingPaise=0,
                discountPaise=0,
                totalPaise=118000,
                inventoryLockToken="lock_signed_fail",
                inventoryLockExpiresAt=2000000000,
            )

        assert "merchantGstin" in str(exc_info.value.errors()[0]["loc"])

    def testTamperedGstinFailsSignatureVerification(self) -> None:
        """Modifying the merchantGstin in the signed payload breaks cryptographic verification."""
        _, merchantSigner, _ = _createSignerTriplet()
        item = _buildStandardCartItem()
        tax = _buildStandardTaxBreakdown()

        signedCart = createSignedCartMandate(
            cartId="M-C-TAMPER",
            merchantSigner=merchantSigner,
            merchantGstin="29AABCU9603R1ZJ",
            merchantStateCode="29",
            buyerDeliveryPincode="560001",
            buyerDeliveryStateCode="29",
            items=[item],
            taxableSubtotalPaise=100000,
            taxBreakdown=tax,
            shippingPaise=0,
            discountPaise=0,
            totalPaise=118000,
            inventoryLockToken="lock_tamper",
            inventoryLockExpiresAt=2000000000,
        )

        tamperedPayload = {
            "buyerDeliveryPincode": signedCart.buyerDeliveryPincode,
            "buyerDeliveryStateCode": signedCart.buyerDeliveryStateCode,
            "cartId": signedCart.cartId,
            "discountPaise": signedCart.discountPaise,
            "inventoryLockExpiresAt": signedCart.inventoryLockExpiresAt,
            "inventoryLockToken": signedCart.inventoryLockToken,
            "items": [i.model_dump() for i in signedCart.items],
            "merchantDid": signedCart.merchantDid,
            "merchantGstin": "27AABCU9603R1ZN",
            "merchantStateCode": signedCart.merchantStateCode,
            "nonce": signedCart.nonce,
            "shippingPaise": signedCart.shippingPaise,
            "taxBreakdown": signedCart.taxBreakdown.model_dump(),
            "taxableSubtotalPaise": signedCart.taxableSubtotalPaise,
            "timestamp": signedCart.timestamp,
            "totalPaise": signedCart.totalPaise,
        }
        tamperedBytes = canonicalizeJson(tamperedPayload)
        assert Ed25519Verifier.verifySignature(merchantSigner.getPublicKeyHex(), tamperedBytes, signedCart.merchantSignature) is False


class TestFastApiSettlementIngressGstinValidation:
    """Integration tests for FastAPI Settlement execution endpoint schema ingress validation."""

    def _buildMandateTripletPayload(self, merchantGstin: str) -> Dict[str, Any]:
        uSigner, mSigner, aSigner = _createSignerTriplet()
        intentM = createSignedIntentMandate(
            mandateId="M-I-INGRESS-001",
            userSigner=uSigner,
            delegatedAgentDid=aSigner.getAgentDid(),
            maxBudgetPaise=200000,
            upiCircleDelegationToken="upi_tok_ingress",
            singleTransactionLimitPaise=200000,
            validUntilTimestamp=2000000000,
        )
        item = _buildStandardCartItem()
        tax = _buildStandardTaxBreakdown()

        cartDict = {
            "cartId": "M-C-INGRESS-001",
            "merchantDid": mSigner.getAgentDid(),
            "merchantGstin": merchantGstin,
            "merchantStateCode": "29",
            "buyerDeliveryPincode": "560001",
            "buyerDeliveryStateCode": "29",
            "items": [item.model_dump()],
            "taxableSubtotalPaise": 100000,
            "taxBreakdown": tax.model_dump(),
            "shippingPaise": 0,
            "discountPaise": 0,
            "totalPaise": 118000,
            "inventoryLockToken": "lock_ingress_001",
            "inventoryLockExpiresAt": 2000000000,
            "nonce": "nonce_cart_ingress",
            "timestamp": 1700000000,
            "merchantSignature": "00" * 64,
        }
        execDict = {
            "executionId": "M-E-INGRESS-001",
            "buyerAgentDid": aSigner.getAgentDid(),
            "intentMandateHash": "00" * 64,
            "cartMandateHash": "00" * 64,
            "settlementAmountPaise": 118000,
            "currency": "INR",
            "upiCircleToken": "upi_tok_ingress",
            "nonce": "nonce_exec_ingress",
            "timestamp": 1700000000,
            "agentSignature": "00" * 64,
        }

        return {
            "intentMandate": intentM.model_dump(),
            "cartMandate": cartDict,
            "executionMandate": execDict,
            "merchantAccount": "acc_merchant_ingress_01",
            "paymentId": "pay_ingress_001",
            "serverTime": 1700000000,
        }

    @pytest.mark.asyncio
    async def testSettlementExecuteIngressInvalidChecksumReturns422(self) -> None:
        """POST /api/v1/settlement/execute with invalid check digit returns 422 Unprocessable Entity."""
        app, routeClient, _ = _configureTestFastApp()
        payload = self._buildMandateTripletPayload(merchantGstin="29AABCU9603R1ZM")

        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/settlement/execute", json=payload)
            assert resp.status_code == 422
            data = resp.json()
            assert "detail" in data
            errorEntry = data["detail"][0]
            assert "merchantGstin" in errorEntry["loc"]
            assert "Luhn Mod-36" in errorEntry["msg"]
            assert len(routeClient._transfers) == 0
            assert len(routeClient._reversals) == 0

    @pytest.mark.asyncio
    async def testSettlementExecuteIngressInvalidLengthReturns422(self) -> None:
        """POST /api/v1/settlement/execute with 14-char GSTIN returns 422."""
        app, routeClient, _ = _configureTestFastApp()
        payload = self._buildMandateTripletPayload(merchantGstin="29AABCU9603R1Z")

        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/settlement/execute", json=payload)
            assert resp.status_code == 422
            assert "merchantGstin" in resp.json()["detail"][0]["loc"]
            assert len(routeClient._transfers) == 0

    @pytest.mark.asyncio
    async def testSettlementExecuteIngressLowercaseReturns422(self) -> None:
        """POST /api/v1/settlement/execute with lowercase GSTIN returns 422."""
        app, routeClient, _ = _configureTestFastApp()
        payload = self._buildMandateTripletPayload(merchantGstin="29aabcu9603r1zj")

        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/settlement/execute", json=payload)
            assert resp.status_code == 422
            assert "merchantGstin" in resp.json()["detail"][0]["loc"]
            assert len(routeClient._transfers) == 0


class TestCrossStateAndPlaceOfSupplyConsistency:
    """Tests cross-consistency between GSTIN state prefixes and delivery PIN derivation."""

    def testIntraStateKarnatakaConsistency(self) -> None:
        """Karnataka GSTIN (29) + Bengaluru PIN (560001 -> 29) matches intra-state state derivation."""
        gstin = VALID_STATE_GSTIN_MAP["29"]
        gstinState = gstin[:2]
        pincode = "560001"
        derivedState = deriveStateCodeFromPincode(pincode)
        assert gstinState == "29"
        assert derivedState == "29"
        assert gstinState == derivedState

    def testInterStateKarnatakaToMaharashtraConsistency(self) -> None:
        """Karnataka GSTIN (29) + Mumbai PIN (400001 -> 27) correctly identifies inter-state supply."""
        gstin = VALID_STATE_GSTIN_MAP["29"]
        gstinState = gstin[:2]
        pincode = "400001"
        derivedState = deriveStateCodeFromPincode(pincode)
        assert gstinState == "29"
        assert derivedState == "27"
        assert gstinState != derivedState


class TestMerchantRegistrarAndMandateEngineValidatorParity:
    """Verifies 100% parity between merchantRegistrar and mandateEngine GSTIN validation."""

    @pytest.mark.parametrize("state_code, valid_gstin", VALID_STATE_GSTIN_MAP.items())
    def testParityOnValidGstins(self, state_code: str, valid_gstin: str) -> None:
        """Both validators return True for all canonical state GSTINs."""
        assert validateGstin(valid_gstin) is True
        assert registrarValidateGstin(valid_gstin) is True

    @pytest.mark.parametrize("invalid_gstin", [
        "29AABCU9603R1ZM",
        "29AAAAA0000A1Z5",
        "27AAPFU0939F1Z0",
        "29aabcu9603r1zj",
        "29AABCU9603R1Z!",
        "00AABCU9603R1Z1",
        "99AABCU9603R1Z0",
        "",
        "SHORT",
    ])
    def testParityOnInvalidGstins(self, invalid_gstin: str) -> None:
        """Both validators return False for all invalid GSTINs."""
        assert validateGstin(invalid_gstin) is False
        assert registrarValidateGstin(invalid_gstin) is False


class TestAdversarialAndFuzzingGstinAttacks:
    """Adversarial fuzzing, injection attacks, and boundary edge cases."""

    @pytest.mark.parametrize("attack_payload", [
        "29AABCU9603R1\x00J",
        "29AABCU9603R1ZJ\r\n",
        "29AABCU9603R1ZJ\u200b",
        " 29AABCU9603R1ZJ ",
        "' OR '1'='1",
        "<script>alert(1)</script>",
        "{\"$gt\": \"\"}",
    ])
    def testAdversarialPayloadRejection(self, attack_payload: str) -> None:
        """Adversarial and malicious payloads fail validation safely without crashing."""
        assert validateGstin(attack_payload) is False
        with pytest.raises(ValidationError):
            _buildDirectCartMandate(merchantGstin=attack_payload)
