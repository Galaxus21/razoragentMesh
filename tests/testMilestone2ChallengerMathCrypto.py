"""Milestone 2 Challenger: AST, Math, Tax, and Cryptographic Hash-Chain Invariants.

Tests:
1. AST, Line Limits & Layout Validation
2. GSTR-1, GSTR-3B Tax Calculations & Integer Paise Math (Enclave & Engine)
3. Mandate Factory Lifecycle & Cryptographic Hash Chain Integrity
"""

import ast
import os
import random
import time
import pytest

from razoragentMesh.packages.mandateEngine.constants.settlementConstants import (
    basisPointsDivisor,
    tcsCgstBasisPoints,
    tcsIgstBasisPoints,
    tcsRateBasisPoints,
    tcsSgstBasisPoints,
)
from razoragentMesh.packages.mandateEngine.crypto.cryptoKeyUtils import generateKeyPair
from razoragentMesh.packages.mandateEngine.crypto.ed25519Signer import Ed25519Signer
from razoragentMesh.packages.mandateEngine.mandates.cartMandateSchema import (
    CartItemSchema,
    CartMandate,
    TaxBreakdownSchema,
)
from razoragentMesh.packages.mandateEngine.mandates.intentMandateSchema import (
    IntentMandate,
)
from razoragentMesh.packages.mandateEngine.mandates.mandateFactory import (
    computeMandateHash,
    createSignedAmendmentMandate,
    createSignedCartMandate,
    createSignedExecutionMandate,
    createSignedIntentMandate,
    verifyMandateChain,
    verifyMandateHashChain,
)
from razoragentMesh.packages.mandateEngine.settlement.settlementExceptions import (
    MandateHashChainMismatchException,
)
from razoragentMesh.packages.mandateEngine.tax.gstrInvoiceEngine import (
    isPlaceOfSupplyIntraState,
)
from razoragentMesh.packages.mandateEngine.tax.gstrInvoiceHtmlRenderer import (
    formatPaiseToInr,
)
from razoragentMesh.packages.mandateEngine.verification.arithmeticEnclave import (
    computeGstBreakdown,
    computeLineItemTotal,
    computeTcsWithholding,
)


class TestMilestone2AstAndLayout:
    """Verifies file length <= 300 lines and function length <= 40 lines."""

    def testAstAndFunctionLengths(self) -> None:
        targetFiles = [
            "razoragentMesh/packages/mandateEngine/mandateApp.py",
            "razoragentMesh/packages/mandateEngine/mandates/mandateFactory.py",
            "razoragentMesh/packages/mandateEngine/tax/gstrInvoiceEngine.py",
            "razoragentMesh/packages/mandateEngine/tax/gstrInvoiceHtmlRenderer.py",
            "razoragentMesh/packages/mandateEngine/verification/budgetGate.py",
        ]
        violations = []
        for f in targetFiles:
            actualPath = f if os.path.exists(f) else f.replace("razoragentMesh/", "")
            with open(actualPath, "r", encoding="utf-8") as fp:
                lines = fp.readlines()
            if len(lines) > 300:
                violations.append(f"{f} exceeds 300 lines ({len(lines)})")
            tree = ast.parse("".join(lines), filename=f)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    fnLen = node.end_lineno - node.lineno + 1
                    if fnLen > 40:
                        violations.append(f"{f} function {node.name} exceeds 40 lines ({fnLen})")
        assert not violations, f"AST Violations: {violations}"


class TestTaxEngineAndIntegerMath:
    """Stress tests GSTR-1 & GSTR-3B tax calculations, slabs, and states."""

    @pytest.mark.parametrize("rate", [0, 5, 12, 18, 28])
    @pytest.mark.parametrize(
        "mState,bState,isIntra",
        [("29", "29", True), ("29", "27", False), ("07", "07", True), ("07", "33", False)],
    )
    def testTaxCalculationPrecision(self, rate: int, mState: str, bState: str, isIntra: bool) -> None:
        assert isPlaceOfSupplyIntraState(mState, bState) == isIntra
        taxable = 12345 * 3
        gst = computeGstBreakdown(taxable, rate, isIntra)
        tcs = computeTcsWithholding(taxable, isIntra)

        if isIntra:
            # CGST and SGST are each the half-rate applied independently, so they are
            # always equal; the total is their sum, not a separately-floored full-rate value.
            expectedCgst = (taxable * rate) // 200
            expectedTotal = expectedCgst * 2
            assert gst.cgstPaise == expectedCgst
            assert gst.sgstPaise == expectedCgst
            assert gst.igstPaise == 0 and gst.totalTaxPaise == expectedTotal
            assert tcs["tcsCgstPaise"] == (taxable * tcsCgstBasisPoints) // basisPointsDivisor
            assert tcs["tcsSgstPaise"] == (taxable * tcsSgstBasisPoints) // basisPointsDivisor
            assert tcs["totalTcsPaise"] == tcs["tcsCgstPaise"] + tcs["tcsSgstPaise"]
            # Section 52 splits the combined rate equally between CGST and SGST.
            assert tcsCgstBasisPoints == tcsSgstBasisPoints
            assert tcsCgstBasisPoints + tcsSgstBasisPoints == tcsRateBasisPoints
        else:
            assert gst.cgstPaise == 0 and gst.sgstPaise == 0
            assert gst.igstPaise == (taxable * rate) // 100
            assert gst.totalTaxPaise == (taxable * rate) // 100
            assert tcs["tcsIgstPaise"] == (taxable * tcsIgstBasisPoints) // basisPointsDivisor
            assert tcs["totalTcsPaise"] == tcs["tcsIgstPaise"]

    def testRandomizedTaxFuzzing1000Items(self) -> None:
        random.seed(1337)
        for _ in range(1000):
            unitPrice = random.randint(1, 10000000)
            qty = random.randint(1, 20)
            rate = random.choice([0, 5, 12, 18, 28])
            isIntra = random.choice([True, False])
            taxable = computeLineItemTotal(unitPrice, qty)
            gst = computeGstBreakdown(taxable, rate, isIntra)
            tcs = computeTcsWithholding(taxable, isIntra)

            assert isinstance(taxable, int) and isinstance(gst.totalTaxPaise, int)
            if isIntra:
                assert gst.cgstPaise == gst.sgstPaise
                assert gst.cgstPaise + gst.sgstPaise == gst.totalTaxPaise
                assert gst.totalTaxPaise == 2 * ((taxable * rate) // 200)
                assert tcs["tcsCgstPaise"] == tcs["tcsSgstPaise"]
            else:
                assert gst.igstPaise == (taxable * rate) // 100
                assert tcs["tcsCgstPaise"] == 0 and tcs["tcsSgstPaise"] == 0

    def testMonetaryStressHugeValue(self) -> None:
        hugeTaxable = 10_000_000_000_000
        hugeGst = computeGstBreakdown(hugeTaxable, 18, isIntraState=True)
        assert hugeGst.cgstPaise == 900_000_000_000
        assert hugeGst.sgstPaise == 900_000_000_000
        assert hugeGst.totalTaxPaise == 1_800_000_000_000
        assert formatPaiseToInr(hugeTaxable) == "₹100000000000.00"


def _buildSampleMandates() -> tuple:
    userSigner = Ed25519Signer(generateKeyPair()[0])
    merchantSigner = Ed25519Signer(generateKeyPair()[0])
    agentSigner = Ed25519Signer(generateKeyPair()[0])
    intent = createSignedIntentMandate(
        mandateId="M-I-TEST-001", userSigner=userSigner,
        delegatedAgentDid=agentSigner.getAgentDid(), maxBudgetPaise=500000,
        upiCircleDelegationToken="tok_upi", singleTransactionLimitPaise=250000,
        authorizedCategories=["electronics"],
    )
    items = [
        CartItemSchema(
            skuId="SKU-PHONE-01", quantity=1, unitPricePaise=100000,
            hsnCode="8517", gstRatePercent=18, lineTotalPaise=100000,
        )
    ]
    cart = createSignedCartMandate(
        cartId="M-C-TEST-001", merchantSigner=merchantSigner,
        merchantGstin="29ABCDE1234F1ZW", merchantStateCode="29",
        buyerDeliveryPincode="560001", buyerDeliveryStateCode="29",
        items=items, taxableSubtotalPaise=100000,
        taxBreakdown=TaxBreakdownSchema(cgstPaise=9000, sgstPaise=9000, igstPaise=0, totalTaxPaise=18000),
        shippingPaise=5000, discountPaise=2000, totalPaise=121000,
        inventoryLockToken="lock_token_abc", inventoryLockExpiresAt=int(time.time()) + 900,
    )
    execution = createSignedExecutionMandate(
        executionId="M-E-TEST-001", buyerAgentSigner=agentSigner,
        intentMandate=intent, cartMandate=cart, settlementAmountPaise=121000,
        upiCircleToken="tok_upi",
    )
    return intent, cart, execution, merchantSigner, agentSigner


class TestMandateFactoryAndCrypto:
    """Stress tests mandate creation, hashing, and anti-tamper verification."""

    def testMandateLifecycleAndChaining(self) -> None:
        intent, cart, execution, _, _ = _buildSampleMandates()
        assert verifyMandateHashChain(intent, cart, execution) is True
        assert verifyMandateChain(intent, cart, execution) is True

    def testMandateTamperingDetection(self) -> None:
        intent, cart, execution, _, _ = _buildSampleMandates()
        tamperedIntent = intent.model_copy(update={"maxBudgetPaise": 999999})
        with pytest.raises(MandateHashChainMismatchException):
            verifyMandateHashChain(tamperedIntent, cart, execution)

        tamperedCart = cart.model_copy(update={"totalPaise": 999999})
        with pytest.raises(MandateHashChainMismatchException):
            verifyMandateHashChain(intent, tamperedCart, execution)

    def testAmendmentMandateDualSignatures(self) -> None:
        _, cart, _, merchantSigner, agentSigner = _buildSampleMandates()
        healedCart = cart.model_copy(update={"cartId": "M-C-HEALED-001"})
        amendment = createSignedAmendmentMandate(
            amendmentId="M-A-TEST-001", buyerAgentSigner=agentSigner,
            merchantSigner=merchantSigner, previousCartMandate=cart,
            newCartMandate=healedCart, substitutedSkuMapping={"SKU-OLD": "SKU-NEW"},
            priceDeltaPaise=0, amendmentReason="Inventory restock",
        )
        assert amendment.previousCartMandateHash == computeMandateHash(cart)
        assert amendment.newCartMandateHash == computeMandateHash(healedCart)
