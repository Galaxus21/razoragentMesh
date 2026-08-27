"""Unified asynchronous HTTP client for RazorAgent Mesh v2.0 commerce ecosystem."""

from typing import Any, Dict, Optional
import httpx

from .agentKeyManager import AgentKeyManager
from .agentMandateBuilder import validateMandateInvariants
from .constants import (
    defaultCurrency,
    defaultLockTtlSeconds,
    defaultPowDifficulty,
    defaultRequestTimeoutSeconds,
    endpointInventoryLock,
    endpointLiveSkuQuote,
    endpointMeshChallenge,
    endpointMeshEscrow,
    endpointMeshEscrowRelease,
    endpointPriceDropAlerts,
    endpointSettlementExecute,
    headerAccept,
    headerBuyerAgentDid,
    headerContentType,
    headerPowChallenge,
    headerPowSolution,
    mimeTypeJson,
)
from .exceptions import (
    Http402RequiredError,
    NetworkClientError,
    SettlementError,
)
from .models import (
    CartMandate,
    EscrowRefundReceipt,
    EscrowSession,
    ExecuteSettlementRequestSchema,
    ExecutionMandate,
    IntentMandate,
    InventoryLockRequest,
    InventoryLockResponse,
    MeshSlaConfig,
    PoWChallenge,
    PriceDropAlertCancelResponse,
    PriceDropAlertRegisterRequest,
    PriceDropAlertResponse,
    SettlementResult,
    SkuQuote,
    SkuQuoteRequest,
)
from .powSolver import PowSolver


class RazorAgentClient:
    """High-performance asynchronous client for autonomous AI buyer agents."""

    def __init__(
        self,
        config: Optional[MeshSlaConfig] = None,
        keyManager: Optional[AgentKeyManager] = None,
        httpClient: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self._config = config or MeshSlaConfig()
        self._keyManager = keyManager or AgentKeyManager.generate()
        self._httpClient = httpClient
        self._ownsClient = httpClient is None

    async def __aenter__(self) -> "RazorAgentClient":
        if self._httpClient is None:
            self._httpClient = httpx.AsyncClient(
                base_url=self._config.gatewayBaseUrl,
                timeout=httpx.Timeout(self._config.timeoutSeconds),
                headers={headerAccept: mimeTypeJson, headerContentType: mimeTypeJson},
            )
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._ownsClient and self._httpClient is not None:
            await self._httpClient.aclose()
            self._httpClient = None

    def _getClient(self) -> httpx.AsyncClient:
        """Returns initialized or active httpx AsyncClient instance."""
        if self._httpClient is not None:
            return self._httpClient
        self._httpClient = httpx.AsyncClient(
            base_url=self._config.gatewayBaseUrl,
            timeout=httpx.Timeout(self._config.timeoutSeconds),
            headers={headerAccept: mimeTypeJson, headerContentType: mimeTypeJson},
        )
        return self._httpClient

    def getKeyManager(self) -> AgentKeyManager:
        """Returns the configured AgentKeyManager instance."""
        return self._keyManager

    def getAgentDid(self) -> str:
        """Returns the buyer agent DID identifier."""
        return self._keyManager.getAgentDid()

    async def getLiveSkuQuote(
        self,
        skuId: str,
        quantity: int = 1,
        deliveryPincode: str = "560001",
        promoCode: Optional[str] = None,
        buyerAgentDid: Optional[str] = None,
    ) -> SkuQuote:
        """Discovers product listing and fetches live, dynamic quote."""
        client = self._getClient()
        agentDid = buyerAgentDid or self.getAgentDid()
        requestModel = SkuQuoteRequest(
            sku_id=skuId,
            quantity=quantity,
            buyer_agent_id=agentDid,
            delivery_pincode=deliveryPincode,
            promo_code=promoCode,
        )
        resp = await client.post(endpointLiveSkuQuote, json=requestModel.model_dump())
        if resp.status_code != 200:
            raise NetworkClientError(f"Quote failed with status {resp.status_code}: {resp.text}", resp.status_code)
        return SkuQuote.model_validate(resp.json())

    async def _handlePowLockRetry(
        self, client: httpx.AsyncClient, reqPayload: Dict[str, Any],
        challengeData: Dict[str, Any], agentDid: str,
    ) -> httpx.Response:
        cToken = challengeData.get("challengeToken", "")
        diffZeros = challengeData.get("powDifficultyZeros", defaultPowDifficulty)
        nonce = PowSolver.solve(cToken, difficultyZeros=diffZeros)
        headers = {
            headerPowChallenge: cToken,
            headerPowSolution: str(nonce),
            headerBuyerAgentDid: agentDid,
        }
        return await client.post(endpointInventoryLock, json=reqPayload, headers=headers)

    async def reserveInventoryLock(
        self,
        skuId: str,
        quantity: int = 1,
        lockTtlSeconds: int = defaultLockTtlSeconds,
        quoteHash: Optional[str] = None,
        buyerAgentDid: Optional[str] = None,
        autoSolvePow: Optional[bool] = None,
    ) -> InventoryLockResponse:
        """Reserves stock inventory with automatic HTTP 402 challenge resolution."""
        client = self._getClient()
        agentDid = buyerAgentDid or self.getAgentDid()
        reqPayload = InventoryLockRequest(
            sku_id=skuId, quantity=quantity, lock_ttl_seconds=lockTtlSeconds,
            buyer_agent_id=agentDid, quote_hash=quoteHash or "default_quote_hash",
        ).model_dump()

        resp = await client.post(endpointInventoryLock, json=reqPayload)
        shouldAutoSolve = self._config.autoSolvePow if autoSolvePow is None else autoSolvePow

        if resp.status_code == 402 and shouldAutoSolve:
            resp = await self._handlePowLockRetry(client, reqPayload, resp.json(), agentDid)

        if resp.status_code == 402:
            cData = resp.json()
            raise Http402RequiredError("PoW or micro-escrow required", cData.get("challengeToken"), cData.get("powDifficultyZeros"))
        if resp.status_code != 200:
            raise NetworkClientError(f"Inventory lock failed with status {resp.status_code}: {resp.text}", resp.status_code)

        return InventoryLockResponse.model_validate(resp.json())

    async def executeSettlement(
        self,
        intentMandate: IntentMandate,
        cartMandate: CartMandate,
        executionMandate: ExecutionMandate,
        merchantAccount: str,
        paymentId: str,
        serverTime: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SettlementResult:
        """Executes 2PC atomic settlement saga with AP2 mandate verification."""
        validateMandateInvariants(intentMandate, cartMandate, executionMandate, serverTime)
        client = self._getClient()
        reqPayload = ExecuteSettlementRequestSchema(
            intentMandate=intentMandate,
            cartMandate=cartMandate,
            executionMandate=executionMandate,
            merchantAccount=merchantAccount,
            paymentId=paymentId,
            serverTime=serverTime,
            metadata=metadata or {},
        ).model_dump()

        resp = await client.post(endpointSettlementExecute, json=reqPayload)
        if resp.status_code != 200:
            raise SettlementError(
                f"Settlement saga rejected with status {resp.status_code}: {resp.text}",
                statusCode=resp.status_code,
                details=resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"body": resp.text},
            )
        return SettlementResult.model_validate(resp.json())

    async def handlePriceDropAlert(
        self,
        skuId: str,
        targetPricePaise: int,
        callbackUrl: str,
        expiresAtUnix: int,
        buyerAgentId: Optional[str] = None,
    ) -> PriceDropAlertResponse:
        """Registers a price drop alert subscription with gateway."""
        client = self._getClient()
        agentDid = buyerAgentId or self.getAgentDid()
        reqPayload = PriceDropAlertRegisterRequest(
            skuId=skuId,
            targetPricePaise=targetPricePaise,
            callbackUrl=callbackUrl,
            buyerAgentId=agentDid,
            expiresAtUnix=expiresAtUnix,
        ).model_dump()

        resp = await client.post(endpointPriceDropAlerts, json=reqPayload)
        if resp.status_code != 200:
            raise NetworkClientError(f"Alert registration failed ({resp.status_code}): {resp.text}", resp.status_code)
        return PriceDropAlertResponse.model_validate(resp.json())

    registerPriceDropAlert = handlePriceDropAlert

    async def cancelPriceDropAlert(self, alertId: str) -> PriceDropAlertCancelResponse:
        """Cancels an active price drop alert subscription."""
        client = self._getClient()
        resp = await client.delete(f"{endpointPriceDropAlerts}/{alertId}")
        if resp.status_code != 200:
            raise NetworkClientError(f"Alert cancellation failed ({resp.status_code}): {resp.text}", resp.status_code)
        return PriceDropAlertCancelResponse.model_validate(resp.json())

    async def getPowChallenge(self) -> PoWChallenge:
        """Requests a fresh PoW challenge token from Layer 2 Gateway."""
        client = self._getClient()
        resp = await client.get(endpointMeshChallenge)
        if resp.status_code != 200:
            raise NetworkClientError(f"Challenge request failed ({resp.status_code}): {resp.text}", resp.status_code)
        return PoWChallenge.model_validate(resp.json())

    async def createEscrowSession(self, initialHoldPaise: int = 5000) -> EscrowSession:
        """Creates a new Layer 2 micro-escrow session."""
        client = self._getClient()
        pld = {"buyerAgentDid": self.getAgentDid(), "initialHoldPaise": initialHoldPaise, "currency": defaultCurrency}
        resp = await client.post(endpointMeshEscrow, json=pld)
        if resp.status_code != 200:
            raise NetworkClientError(f"Escrow creation failed ({resp.status_code}): {resp.text}", resp.status_code)
        return EscrowSession.model_validate(resp.json())

    async def releaseEscrow(self, sessionToken: str) -> EscrowRefundReceipt:
        """Releases and refunds unused micro-escrow balance."""
        client = self._getClient()
        resp = await client.post(endpointMeshEscrowRelease, json={"sessionToken": sessionToken})
        if resp.status_code != 200:
            raise NetworkClientError(f"Escrow release failed ({resp.status_code}): {resp.text}", resp.status_code)
        return EscrowRefundReceipt.model_validate(resp.json())


__all__ = [
    "RazorAgentClient",
]
