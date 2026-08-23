"""Unit test suite for merchant negotiation policy schema and boundary constraints."""

import json
import pytest
from pydantic import ValidationError

from razoragentMesh.packages.merchantApi.src.constants.merchantConstants import (
    redisMerchantPolicyKeyPrefix,
)
from razoragentMesh.packages.merchantApi.src.schemas.policySchema import (
    NegotiationPolicy,
)

# Test boundary and validation constants
testMerchantDid: str = "did:razoragent:merchant:tanishq01"
validMarginFloorBps: int = 500
validMinimumOrderQuantity: int = 10
validAutoAcceptSpreadPaise: int = 100
validMaxNegotiationTurns: int = 5
fixedTimestamp: int = 1700000000
invalidHighMarginFloorBps: int = 10500
invalidNegativeMarginFloorBps: int = -50
zeroMoq: int = 0
negativeSpreadPaise: int = -10


def testNegotiationPolicySchemaValidation() -> None:
    """Verifies valid negotiation policy instantiation and model immutability."""
    policy = NegotiationPolicy(
        merchantDid=testMerchantDid,
        marginFloorBps=validMarginFloorBps,
        minimumOrderQuantity=validMinimumOrderQuantity,
        autoAcceptSpreadPaise=validAutoAcceptSpreadPaise,
        maxNegotiationTurns=validMaxNegotiationTurns,
        createdAtTimestamp=fixedTimestamp,
        updatedAtTimestamp=fixedTimestamp,
    )

    assert policy.merchantDid == testMerchantDid
    assert policy.marginFloorBps == validMarginFloorBps
    assert policy.minimumOrderQuantity == validMinimumOrderQuantity
    assert policy.maxNegotiationTurns == validMaxNegotiationTurns

    with pytest.raises(ValidationError):
        policy.marginFloorBps = 800  # type: ignore[misc]


def testNegotiationPolicyRejectsInvalidMarginFloor() -> None:
    """Verifies rejection of margin floors exceeding 10000 bps or negative values."""
    with pytest.raises(ValidationError):
        NegotiationPolicy(
            merchantDid=testMerchantDid,
            marginFloorBps=invalidHighMarginFloorBps,
            createdAtTimestamp=fixedTimestamp,
            updatedAtTimestamp=fixedTimestamp,
        )

    with pytest.raises(ValidationError):
        NegotiationPolicy(
            merchantDid=testMerchantDid,
            marginFloorBps=invalidNegativeMarginFloorBps,
            createdAtTimestamp=fixedTimestamp,
            updatedAtTimestamp=fixedTimestamp,
        )


def testNegotiationPolicyRejectsZeroMoq() -> None:
    """Verifies that minimum order quantity below 1 is strictly rejected."""
    with pytest.raises(ValidationError):
        NegotiationPolicy(
            merchantDid=testMerchantDid,
            marginFloorBps=validMarginFloorBps,
            minimumOrderQuantity=zeroMoq,
            createdAtTimestamp=fixedTimestamp,
            updatedAtTimestamp=fixedTimestamp,
        )


def testRedisKeyFormat() -> None:
    """Verifies merchant policy Redis key namespace and prefix structure."""
    expectedRedisKey = f"mesh:merchant:policy:{testMerchantDid}"
    actualRedisKey = f"{redisMerchantPolicyKeyPrefix}{testMerchantDid}"
    assert actualRedisKey == expectedRedisKey


def testPolicyJsonRoundTrip() -> None:
    """Verifies JSON serialization and deserialization roundtrip without precision drift."""
    originalPolicy = NegotiationPolicy(
        merchantDid=testMerchantDid,
        marginFloorBps=validMarginFloorBps,
        minimumOrderQuantity=validMinimumOrderQuantity,
        autoAcceptSpreadPaise=validAutoAcceptSpreadPaise,
        maxNegotiationTurns=validMaxNegotiationTurns,
        createdAtTimestamp=fixedTimestamp,
        updatedAtTimestamp=fixedTimestamp,
    )

    serializedJson = originalPolicy.model_dump_json()
    parsedData = json.loads(serializedJson)

    assert parsedData["merchantDid"] == testMerchantDid
    assert parsedData["marginFloorBps"] == validMarginFloorBps
    assert parsedData["autoAcceptSpreadPaise"] == validAutoAcceptSpreadPaise
    assert isinstance(parsedData["autoAcceptSpreadPaise"], int)

    reconstructedPolicy = NegotiationPolicy.model_validate_json(serializedJson)
    assert reconstructedPolicy == originalPolicy


def testAutoAcceptSpreadConstraint() -> None:
    """Verifies non-negative constraint on auto-accept spread in integer paise."""
    with pytest.raises(ValidationError):
        NegotiationPolicy(
            merchantDid=testMerchantDid,
            marginFloorBps=validMarginFloorBps,
            autoAcceptSpreadPaise=negativeSpreadPaise,
            createdAtTimestamp=fixedTimestamp,
            updatedAtTimestamp=fixedTimestamp,
        )

    zeroSpreadPolicy = NegotiationPolicy(
        merchantDid=testMerchantDid,
        marginFloorBps=validMarginFloorBps,
        autoAcceptSpreadPaise=0,
        createdAtTimestamp=fixedTimestamp,
        updatedAtTimestamp=fixedTimestamp,
    )
    assert zeroSpreadPolicy.autoAcceptSpreadPaise == 0
