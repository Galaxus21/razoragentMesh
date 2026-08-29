"""Tests that money-moving Route calls are idempotent under retry.

A transfer or reversal that times out may already have been accepted by the provider. Both the
inline compensation path and the DLQ retry worker re-issue such calls, so without a stable
idempotency key the same money movement can be executed twice. The DLQ has carried an
`idempotencyKey` field since it was written, but never sent it to the client.
"""

import pytest

from razoragentMesh.packages.mandateEngine.settlement.razorpayRouteClient import (
    RazorpayRouteClient,
    RouteTransferRequest,
    headerIdempotencyKey,
)
from razoragentMesh.packages.mandateEngine.settlement.twoPhaseCommitSaga import (
    _buildReversalIdempotencyKey,
    _buildTransferIdempotencyKey,
)

merchantAccount: str = "acc_merchant_idem"
paymentId: str = "pay_idem_001"


def _request(account: str = merchantAccount, purpose: str = "merchant_net_settlement") -> RouteTransferRequest:
    return RouteTransferRequest(
        account=account, amount=100000, notes={"purpose": purpose, "paymentId": paymentId},
    )


@pytest.mark.asyncio
async def testRetryingATransferWithTheSameKeyDoesNotPayTwice() -> None:
    """Re-issuing an identical transfer returns the original rather than creating a second."""
    client = RazorpayRouteClient(isMockMode=True)
    request = _request()
    key = _buildTransferIdempotencyKey(request, paymentId)

    first = await client.createTransfer(request, idempotencyKey=key)
    second = await client.createTransfer(request, idempotencyKey=key)

    assert first.id == second.id
    assert len(client._transfers) == 1


@pytest.mark.asyncio
async def testDistinctSplitLegsRemainIndependent() -> None:
    """Different recipients of the same payment must not collapse into one transfer."""
    client = RazorpayRouteClient(isMockMode=True)
    merchantLeg = _request()
    protocolLeg = _request(account="acc_protocol_idem", purpose="protocol_fee")

    first = await client.createTransfer(
        merchantLeg, idempotencyKey=_buildTransferIdempotencyKey(merchantLeg, paymentId))
    second = await client.createTransfer(
        protocolLeg, idempotencyKey=_buildTransferIdempotencyKey(protocolLeg, paymentId))

    assert first.id != second.id
    assert len(client._transfers) == 2


@pytest.mark.asyncio
async def testInlineAndDlqReversalPathsShareOneKey() -> None:
    """The inline compensation path and the DLQ worker must agree on the reversal key.

    If they diverged, a reversal that timed out inline and was then retried by the worker
    would refund the same transfer twice.
    """
    from razoragentMesh.packages.mandateEngine.settlement.compensationDlq import CompensationDlq

    transferId = "trf_shared_key_001"
    dlq = CompensationDlq(redisClient=None)
    event = await dlq.enqueueReversal(
        transferId=transferId, amountPaise=100000, recipientAccountId=merchantAccount,
        paymentId=paymentId, reason="timeout during inline reversal",
    )

    assert event.idempotencyKey == _buildReversalIdempotencyKey(transferId)


class _HeaderCapturingClient:
    """Minimal httpx-compatible double that records the headers it was called with."""

    def __init__(self) -> None:
        self.capturedHeaders: dict = {}

    async def request(self, method, url, json=None, headers=None, auth=None, timeout=None):
        self.capturedHeaders = dict(headers or {})

        class _Response:
            status_code = 200

            @staticmethod
            def json():
                return {"id": "trf_live_001", "account": merchantAccount, "amount": 100000}

        return _Response()


@pytest.mark.asyncio
async def testIdempotencyKeyIsActuallySentAsAHeader() -> None:
    """The key must reach the provider on the wire, not merely be computed and discarded."""
    capturingClient = _HeaderCapturingClient()
    client = RazorpayRouteClient(isMockMode=False, httpClient=capturingClient)
    request = _request()

    await client.createTransfer(request, idempotencyKey="trf_idem_expected")

    assert capturingClient.capturedHeaders.get(headerIdempotencyKey) == "trf_idem_expected"


@pytest.mark.asyncio
async def testNoIdempotencyHeaderWhenNoKeySupplied() -> None:
    """Control: the header is absent rather than sent empty when no key is provided."""
    capturingClient = _HeaderCapturingClient()
    client = RazorpayRouteClient(isMockMode=False, httpClient=capturingClient)

    await client.createTransfer(_request(), idempotencyKey=None)

    assert headerIdempotencyKey not in capturingClient.capturedHeaders
