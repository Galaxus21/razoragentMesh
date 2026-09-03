"""Unified asynchronous HTTP client for RazorAgent Mesh v2.0 commerce ecosystem."""

from typing import Any, Dict, Optional
import httpx

from .agentKeyManager import AgentKeyManager
from .agentMandateBuilder import validateMandateInvariants
from .constants import (
    defaultInitialEscrowHoldPaise,
    defaultLockTtlSeconds,
    defaultPowDifficulty,
    defaultRequestTimeoutSeconds,
    endpointInventoryLock,
    endpointLiveSkuQuote,
    endpointMeshChallenge,
    endpointMeshEscrow,
    endpointMeshEscrowRelease,
    endpointMeshNegotiate,
    endpointPriceDropAlerts,
    endpointSettlementExecute,
    escrowCreateSuccessStatuses,
    headerAccept,
    headerBuyerAgentDid,
    headerContentType,
    headerEscrowToken,
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
            self._httpClient = self._buildClient()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._ownsClient and self._httpClient is not None:
            await self._httpClient.aclose()
            self._httpClient = None

    def _buildClient(self) -> httpx.AsyncClient:
        """Builds the shared transport.

        Deliberately carries no `base_url`. Every endpoint this client calls is resolved to an
        absolute URL by `_resolveUrl`, because the four routes below are served by three
        different services -- binding one base URL here is what made seven of eight calls 404.
        """
        return httpx.AsyncClient(
            timeout=httpx.Timeout(self._config.timeoutSeconds),
            headers={headerAccept: mimeTypeJson, headerContentType: mimeTypeJson},
        )

    def _getClient(self) -> httpx.AsyncClient:
        """Returns initialized or active httpx AsyncClient instance."""
        if self._httpClient is not None:
            return self._httpClient
        self._httpClient = self._buildClient()
        return self._httpClient

    def _resolveUrl(self, endpoint: str) -> str:
        """Resolves an endpoint constant to an absolute URL on the service that serves it.

        The TypeScript client (`packages/buyerSdkTs/src/razorAgentClient.ts`) has always kept
        `_mandateEngineUrl`, `_mcpServerUrl` and `_x402GatewayUrl` apart and picked per call.
        This is the same rule, expressed as one table instead of three fields, so that a reader
        can check the caller/host pairing in one place. `MeshSlaConfig` declared all four base
        URLs from the start; only `gatewayBaseUrl` was ever read.
        """
        for prefix, baseUrl in self._serviceRoutingTable():
            if endpoint.startswith(prefix):
                return f"{baseUrl.rstrip('/')}{endpoint}"
        # An endpoint with no entry is a routing bug, not a fallback case: silently sending it to
        # the mandate engine is precisely the defect this method exists to prevent.
        raise NetworkClientError(
            f"No service is configured for endpoint '{endpoint}'. Add it to the routing table in "
            "RazorAgentClient._serviceRoutingTable.",
            None,
        )

    def _serviceRoutingTable(self) -> tuple:
        """Maps each route prefix to the base URL of the service that serves it.

        Ordered longest-prefix-first so a more specific route cannot be shadowed by a shorter one.
        """
        config = self._config
        mcpBaseUrl = config.mcpBaseUrl or config.gatewayBaseUrl
        x402BaseUrl = config.x402GatewayBaseUrl or config.gatewayBaseUrl
        return (
            (endpointSettlementExecute, config.gatewayBaseUrl),
            (endpointMeshEscrowRelease, x402BaseUrl),
            (endpointMeshEscrow, x402BaseUrl),
            (endpointMeshChallenge, x402BaseUrl),
            (endpointMeshNegotiate, x402BaseUrl),
            (endpointPriceDropAlerts, x402BaseUrl),
            (endpointLiveSkuQuote, mcpBaseUrl),
            (endpointInventoryLock, mcpBaseUrl),
        )

    def getKeyManager(self) -> AgentKeyManager:
        """Returns the configured AgentKeyManager instance."""
        return self._keyManager

    def getAgentDid(self) -> str:
        """Returns the buyer agent DID identifier."""
        return self._keyManager.getAgentDid()

    async def getLiveSkuQuote(
        self,
        skuId: str,
        deliveryPincode: str,
        quantity: int = 1,
        promoCode: Optional[str] = None,
        buyerAgentDid: Optional[str] = None,
    ) -> SkuQuote:
        """Discovers product listing and fetches live, dynamic quote."""
        client = self._getClient()
        agentDid = buyerAgentDid or self.getAgentDid()
        # The MCP HTTP face serves quotes as GET with query parameters. This used to POST a body
        # to /api/v1/quotes/live, a route nothing has ever served, so every call 404'd -- invisible
        # to the SDK's own suite, which mocks the transport and answers whatever it is asked.
        queryParameters = {
            "skuId": skuId,
            "quantity": str(quantity),
            "buyerAgentDid": agentDid,
            "deliveryPincode": deliveryPincode,
        }
        if promoCode:
            queryParameters["promoCode"] = promoCode
        resp = await client.get(self._resolveUrl(endpointLiveSkuQuote), params=queryParameters)
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
        return await client.post(
            self._resolveUrl(endpointInventoryLock), json=reqPayload, headers=headers
        )

    async def reserveInventoryLock(
        self,
        skuId: str,
        quoteHash: str,
        quantity: int = 1,
        lockTtlSeconds: int = defaultLockTtlSeconds,
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

        resp = await client.post(self._resolveUrl(endpointInventoryLock), json=reqPayload)
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

        resp = await client.post(self._resolveUrl(endpointSettlementExecute), json=reqPayload)
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

        resp = await client.post(self._resolveUrl(endpointPriceDropAlerts), json=reqPayload)
        if resp.status_code != 200:
            raise NetworkClientError(f"Alert registration failed ({resp.status_code}): {resp.text}", resp.status_code)
        return PriceDropAlertResponse.model_validate(resp.json())

    registerPriceDropAlert = handlePriceDropAlert

    async def cancelPriceDropAlert(self, alertId: str) -> PriceDropAlertCancelResponse:
        """Cancels an active price drop alert subscription."""
        client = self._getClient()
        resp = await client.delete(self._resolveUrl(f"{endpointPriceDropAlerts}/{alertId}"))
        if resp.status_code != 200:
            raise NetworkClientError(f"Alert cancellation failed ({resp.status_code}): {resp.text}", resp.status_code)
        return PriceDropAlertCancelResponse.model_validate(resp.json())

    async def getPowChallenge(self) -> PoWChallenge:
        """Requests a fresh PoW challenge token from Layer 2 Gateway."""
        client = self._getClient()
        resp = await client.get(self._resolveUrl(endpointMeshChallenge))
        if resp.status_code != 200:
            raise NetworkClientError(f"Challenge request failed ({resp.status_code}): {resp.text}", resp.status_code)
        return PoWChallenge.model_validate(resp.json())

    async def createEscrowSession(
        self, initialHoldPaise: int = defaultInitialEscrowHoldPaise
    ) -> EscrowSession:
        """Creates a new micro-escrow session on the x402-INR gateway."""
        client = self._getClient()
        # EscrowCreateRequest is extra="forbid" and declares exactly these two fields, so a third
        # key -- this used to send `currency` -- is rejected by the route as a 422.
        pld = {"buyerAgentDid": self.getAgentDid(), "initialHoldPaise": initialHoldPaise}
        resp = await client.post(self._resolveUrl(endpointMeshEscrow), json=pld)
        # The route declares status_code=HTTP_201_CREATED. Accepting only 200 turned every
        # SUCCESSFUL escrow creation into a NetworkClientError.
        if resp.status_code not in escrowCreateSuccessStatuses:
            raise NetworkClientError(f"Escrow creation failed ({resp.status_code}): {resp.text}", resp.status_code)
        return EscrowSession.model_validate(resp.json())

    async def releaseEscrow(self, sessionToken: str) -> EscrowRefundReceipt:
        """Releases and refunds unused micro-escrow balance."""
        client = self._getClient()
        # The token travels as a request HEADER, not in the body: escrowRoute.releaseEscrow takes
        # `sessionToken: str = Header(..., alias=headerEscrowToken)` and has no body model at all,
        # so posting {"sessionToken": ...} was answered with a 422 every time.
        resp = await client.post(
            self._resolveUrl(endpointMeshEscrowRelease),
            headers={headerEscrowToken: sessionToken},
        )
        if resp.status_code != 200:
            raise NetworkClientError(f"Escrow release failed ({resp.status_code}): {resp.text}", resp.status_code)
        return EscrowRefundReceipt.model_validate(resp.json())


__all__ = [
    "RazorAgentClient",
]
