"""Unit tests for Mandate Patcher core substitution and Ed25519 cryptographic linkage."""

import time
from typing import Any, Dict
import pytest

from razoragentMesh.packages.mandateEngine.crypto.cryptoKeyUtils import (
    extractPublicKeyFromDid,
)
from razoragentMesh.packages.mandateEngine.crypto.ed25519Signer import Ed25519Signer
from razoragentMesh.packages.mandateEngine.crypto.ed25519Verifier import Ed25519Verifier
from razoragentMesh.packages.mandateEngine.mandates.cartMandateSchema import (
    CartItemSchema,
    CartMandate,
    TaxBreakdownSchema,
)
from razoragentMesh.packages.mandateEngine.mandates.mandateFactory import (
    createSignedCartMandate,
)
from razoragentMesh.packages.mandateEngine.verification.signatureChainVerifier import (
    computeMandateHash,
)
from razoragentMesh.packages.vectorHealer.src.patching.cartDiffGenerator import (
    generateCartDiff,
)
from razoragentMesh.packages.vectorHealer.src.patching.mandatePatcher import (
    MandatePatcher,
)

testMerchantGstin = "29AABCU9603R1ZJ"
testStateCode = "29"
testDeliveryPincode = "560001"


def _createBaseCart(
    merchantSigner: Ed25519Signer, unitPricePaise: int, skuId: str = "SKU-ORIG-001",
) -> CartMandate:
    """Constructs a deterministic signed CartMandate for patcher testing."""
    now = int(time.time())
    totalTax = (unitPricePaise * 18) // 100
    cgst, sgst = totalTax // 2, totalTax // 2
    item = CartItemSchema(
        skuId=skuId, quantity=1, unitPricePaise=unitPricePaise,
        hsnCode="84713010", gstRatePercent=18, lineTotalPaise=unitPricePaise,
    )
    taxBreakdown = TaxBreakdownSchema(cgstPaise=cgst, sgstPaise=sgst, igstPaise=0, totalTaxPaise=totalTax)
    return createSignedCartMandate(
        cartId=f"cart_{skuId.lower()}", merchantSigner=merchantSigner,
        merchantGstin=testMerchantGstin, merchantStateCode=testStateCode,
        buyerDeliveryPincode=testDeliveryPincode, buyerDeliveryStateCode=testStateCode,
        items=[item], taxableSubtotalPaise=unitPricePaise, taxBreakdown=taxBreakdown,
        shippingPaise=0, discountPaise=0, totalPaise=unitPricePaise + totalTax,
        inventoryLockToken="lock_base_token", inventoryLockExpiresAt=now + 60, timestamp=now,
    )



def testMandatePatcherSingleItemSubstitution(agentKeyFixtures: Dict[str, Any]) -> None:
    """Verifies single item stock substitution and healed cart metadata."""
    buyerSigner = Ed25519Signer(agentKeyFixtures["buyerAgent"]["privateKeyHex"])
    merchantSigner = Ed25519Signer(agentKeyFixtures["merchantNode"]["privateKeyHex"])
    origCart = _createBaseCart(merchantSigner, unitPricePaise=100000, skuId="SKU-ORIG-001")
    patcher = MandatePatcher()

    amendment, healedCart = patcher.patchCartMandate(
        originalCartMandate=origCart,
        failedSkuId="SKU-ORIG-001",
        substituteSkuId="SKU-SUB-001",
        substituteUnitPricePaise=105000,
        substituteGstRatePercent=18,
        substituteHsnCode="84713010",
        requestedQuantity=1,
        buyerAgentSigner=buyerSigner,
        merchantSigner=merchantSigner,
    )

    assert amendment.substitutedSkuMapping["SKU-ORIG-001"] == "SKU-SUB-001"
    assert amendment.priceDeltaPaise == 5000
    assert len(healedCart.items) == 1
    assert healedCart.items[0].skuId == "SKU-SUB-001"
    assert healedCart.items[0].unitPricePaise == 105000
    assert healedCart.totalPaise == 123900


def testMandatePatcherDualEd25519Signatures(agentKeyFixtures: Dict[str, Any]) -> None:
    """Verifies dual Ed25519 signatures and tamper detection on amendment mandate."""
    buyerSigner = Ed25519Signer(agentKeyFixtures["buyerAgent"]["privateKeyHex"])
    merchantSigner = Ed25519Signer(agentKeyFixtures["merchantNode"]["privateKeyHex"])
    origCart = _createBaseCart(merchantSigner, unitPricePaise=100000)
    patcher = MandatePatcher()

    amendment, _ = patcher.patchCartMandate(
        originalCartMandate=origCart,
        failedSkuId="SKU-ORIG-001",
        substituteSkuId="SKU-SUB-001",
        substituteUnitPricePaise=105000,
        substituteGstRatePercent=18,
        substituteHsnCode="84713010",
        requestedQuantity=1,
        buyerAgentSigner=buyerSigner,
        merchantSigner=merchantSigner,
    )

    buyerPub = extractPublicKeyFromDid(buyerSigner.getAgentDid())
    merchantPub = extractPublicKeyFromDid(merchantSigner.getAgentDid())
    unsignedDict = {
        k: v for k, v in amendment.model_dump().items()
        if k not in ("agentSignature", "merchantSignature")
    }

    assert Ed25519Verifier.verifyPayloadSignature(buyerPub, unsignedDict, amendment.agentSignature)
    assert Ed25519Verifier.verifyPayloadSignature(merchantPub, unsignedDict, amendment.merchantSignature)

    tampered = dict(unsignedDict)
    tampered["priceDeltaPaise"] = 999999
    assert not Ed25519Verifier.verifyPayloadSignature(buyerPub, tampered, amendment.agentSignature)


def testMandatePatcherOriginalAndAmendedCartHashLinkage(
    agentKeyFixtures: Dict[str, Any],
) -> None:
    """Verifies AP2 triple-hash linkage binding original and healed CartMandates."""
    buyerSigner = Ed25519Signer(agentKeyFixtures["buyerAgent"]["privateKeyHex"])
    merchantSigner = Ed25519Signer(agentKeyFixtures["merchantNode"]["privateKeyHex"])
    origCart = _createBaseCart(merchantSigner, unitPricePaise=100000)
    patcher = MandatePatcher()

    amendment, healedCart = patcher.patchCartMandate(
        originalCartMandate=origCart,
        failedSkuId="SKU-ORIG-001",
        substituteSkuId="SKU-SUB-001",
        substituteUnitPricePaise=105000,
        substituteGstRatePercent=18,
        substituteHsnCode="84713010",
        requestedQuantity=1,
        buyerAgentSigner=buyerSigner,
        merchantSigner=merchantSigner,
    )

    expectedOrigHash = computeMandateHash(origCart)
    expectedHealedHash = computeMandateHash(healedCart)

    assert amendment.previousCartMandateHash == expectedOrigHash
    assert amendment.newCartMandateHash == expectedHealedHash


def testGenerateCartDiffPaiseCalculation(agentKeyFixtures: Dict[str, Any]) -> None:
    """Verifies exact integer paise delta calculation across various scenarios."""
    merchantSigner = Ed25519Signer(agentKeyFixtures["merchantNode"]["privateKeyHex"])
    origCart = _createBaseCart(merchantSigner, unitPricePaise=50000, skuId="SKU-BASE")

    diffHigher = generateCartDiff(origCart, "SKU-BASE", 55000)
    assert diffHigher == 5000

    diffLower = generateCartDiff(origCart, "SKU-BASE", 42000)
    assert diffLower == -8000

    diffEqual = generateCartDiff(origCart, "SKU-BASE", 50000)
    assert diffEqual == 0

    diffUnknown = generateCartDiff(origCart, "SKU-NONEXISTENT", 60000)
    assert diffUnknown == 60000


def testMandatePatcherInventoryLockRefresh(agentKeyFixtures: Dict[str, Any]) -> None:
    """Verifies that healed CartMandate receives fresh inventory lock token and TTL."""
    buyerSigner = Ed25519Signer(agentKeyFixtures["buyerAgent"]["privateKeyHex"])
    merchantSigner = Ed25519Signer(agentKeyFixtures["merchantNode"]["privateKeyHex"])
    origCart = _createBaseCart(merchantSigner, unitPricePaise=100000)
    patcher = MandatePatcher()

    beforeTime = int(time.time())
    _, healedCart = patcher.patchCartMandate(
        originalCartMandate=origCart,
        failedSkuId="SKU-ORIG-001",
        substituteSkuId="SKU-LOCK-REFRESH",
        substituteUnitPricePaise=100000,
        substituteGstRatePercent=18,
        substituteHsnCode="84713010",
        requestedQuantity=1,
        buyerAgentSigner=buyerSigner,
        merchantSigner=merchantSigner,
    )

    assert healedCart.inventoryLockToken == "lock_token_healed_sku-lock-refresh"
    assert healedCart.inventoryLockExpiresAt >= beforeTime + 60


def testMandatePatcherUpwardAndDownwardPriceDeltas(
    agentKeyFixtures: Dict[str, Any],
) -> None:
    """Verifies downward and upward price delta computations in patched mandates."""
    buyerSigner = Ed25519Signer(agentKeyFixtures["buyerAgent"]["privateKeyHex"])
    merchantSigner = Ed25519Signer(agentKeyFixtures["merchantNode"]["privateKeyHex"])
    origCart = _createBaseCart(merchantSigner, unitPricePaise=100000)
    patcher = MandatePatcher()

    amendCheap, healedCheap = patcher.patchCartMandate(
        originalCartMandate=origCart,
        failedSkuId="SKU-ORIG-001",
        substituteSkuId="SKU-SUB-CHEAP",
        substituteUnitPricePaise=80000,
        substituteGstRatePercent=18,
        substituteHsnCode="84713010",
        requestedQuantity=1,
        buyerAgentSigner=buyerSigner,
        merchantSigner=merchantSigner,
    )
    assert amendCheap.priceDeltaPaise == -20000
    assert healedCheap.totalPaise == 94400

    amendExp, healedExp = patcher.patchCartMandate(
        originalCartMandate=origCart,
        failedSkuId="SKU-ORIG-001",
        substituteSkuId="SKU-SUB-EXP",
        substituteUnitPricePaise=110000,
        substituteGstRatePercent=18,
        substituteHsnCode="84713010",
        requestedQuantity=1,
        buyerAgentSigner=buyerSigner,
        merchantSigner=merchantSigner,
    )
    assert amendExp.priceDeltaPaise == 10000
    assert healedExp.totalPaise == 129800
