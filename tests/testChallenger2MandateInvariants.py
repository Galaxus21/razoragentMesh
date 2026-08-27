"""Challenger 2: Mandate Engine Export Completeness, Model Immutability, and Financial Invariants.

Tests:
1. Symbol Export & Interface Conformance
2. Model Immutability and Strict Validation
3. AST-Level No Float in Monetary Calculations
4. Arithmetic Enclave Type Enforcement
5. GST Penny Conservation and Split Manifest Sum Invariants
"""

import ast
import inspect
import os
import random
import pytest

from razoragentMesh.packages.mandateEngine import (
    ArithmeticDriftException,
    CartItemSchema,
    ExecuteSettlementRequestSchema,
    PaymentCaptureResponse,
    RouteTransferRequest,
    RouteTransferResponse,
    SettlementResult,
    SplitTransferManifest,
    TaxBreakdownSchema,
    TransferReversalResponse,
    buildSplitManifest,
    computeCartSettlementTotal,
    computeGstBreakdown,
    computeLineItemTotal,
    computeTcsWithholding,
    createSignedCartMandate,
    validateIntegerPaise,
)
from razoragentMesh.packages.mandateEngine.crypto.cryptoKeyUtils import generateKeyPair
from razoragentMesh.packages.mandateEngine.crypto.ed25519Signer import Ed25519Signer
import razoragentMesh.packages.mandateEngine as mandateEngineModule


def testMandateEngineExportCompleteness() -> None:
    """Verifies all required symbols are present in __all__ and on module."""
    requiredSymbols = [
        "createMandateApp", "mandateApp", "mandateEnginePort", "SettlementOrchestrator",
        "TwoPhaseCommitSaga", "SplitTransferManifest", "buildSplitManifest", "RazorpayRouteClient",
        "computeCartSettlementTotal", "ExecuteSettlementRequest", "ExecuteSettlementRequestSchema",
        "mandateAppLifespan", "validateIntegerPaise", "computeLineItemTotal",
        "computeGstBreakdown", "computeTcsWithholding",
    ]
    for sym in requiredSymbols:
        assert hasattr(mandateEngineModule, sym), f"Missing symbol on mandateEngine: {sym}"
        assert sym in mandateEngineModule.__all__, f"Symbol {sym} missing from mandateEngine.__all__"


def testModelImmutabilityAndStrictValidation() -> None:
    """Verifies Pydantic models are immutable (frozen) and forbid extra attributes."""
    modelsToTest = [
        ExecuteSettlementRequestSchema, SplitTransferManifest, RouteTransferRequest,
        RouteTransferResponse, PaymentCaptureResponse, TransferReversalResponse, SettlementResult,
    ]
    for modelCls in modelsToTest:
        assert modelCls.model_config.get("frozen") is True, f"{modelCls.__name__} must be frozen"
        assert modelCls.model_config.get("extra") == "forbid", f"{modelCls.__name__} must forbid extra fields"


def testAstLevelNoFloatInMonetaryCalculations() -> None:
    """AST-level audit ensuring no float casting or float division in arithmeticEnclave."""
    packageDir = os.path.dirname(inspect.getfile(computeCartSettlementTotal))
    arithmeticPath = os.path.join(packageDir, "arithmeticEnclave.py")

    with open(arithmeticPath, "r", encoding="utf-8") as f:
        sourceCode = f.read()

    tree = ast.parse(sourceCode, filename=arithmeticPath)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "float":
            pytest.fail(f"Illegal float() call found in arithmeticEnclave.py at line {node.lineno}")
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            pytest.fail(f"Illegal float division '/' found in arithmeticEnclave.py at line {node.lineno}; must use '//'")


def testArithmeticEnclaveRejectsNonIntegers() -> None:
    """Verifies all arithmetic enclave functions raise ArithmeticDriftException on non-int."""
    invalidValues = [10.5, 0.0, 1e4, "100", None, True, False, [100], {"val": 100}]
    for val in invalidValues:
        with pytest.raises(ArithmeticDriftException):
            validateIntegerPaise(val, "testField")
        with pytest.raises(ArithmeticDriftException):
            computeLineItemTotal(val, 1)  # type: ignore
        with pytest.raises(ArithmeticDriftException):
            computeLineItemTotal(100, val)  # type: ignore
        with pytest.raises(ArithmeticDriftException):
            computeGstBreakdown(val, 18, True)  # type: ignore
        with pytest.raises(ArithmeticDriftException):
            computeGstBreakdown(1000, val, True)  # type: ignore
        with pytest.raises(ArithmeticDriftException):
            computeTcsWithholding(val, True)  # type: ignore
        with pytest.raises(ArithmeticDriftException):
            computeCartSettlementTotal(val, 100, 0, 0)  # type: ignore


def testGstPennyConservationFuzz() -> None:
    """Property-based fuzz test for GST penny conservation across 1,000 odd values."""
    random.seed(42)
    rates = [0, 5, 12, 18, 28]

    for _ in range(1000):
        subtotalPaise = random.randint(0, 10000000)
        rate = random.choice(rates)
        for isIntra in [True, False]:
            breakdown = computeGstBreakdown(subtotalPaise, rate, isIntra)
            cgst, sgst, igst = breakdown["cgstPaise"], breakdown["sgstPaise"], breakdown["igstPaise"]
            totalTax = breakdown["totalTaxPaise"]
            assert totalTax == cgst + sgst + igst
            if isIntra:
                assert igst == 0 and (cgst + sgst == totalTax) and (sgst >= cgst)
            else:
                assert cgst == 0 and sgst == 0 and (igst == totalTax)


def testCartSettlementTotalInvariantFuzz() -> None:
    """Fuzz test for cart settlement total integer arithmetic conservation."""
    random.seed(1337)
    for _ in range(1000):
        subtotal = random.randint(0, 5000000)
        tax = random.randint(0, 1000000)
        shipping = random.randint(0, 50000)
        discount = random.randint(0, subtotal + tax + shipping)
        gross = computeCartSettlementTotal(subtotal, tax, shipping, discount)
        assert gross == subtotal + tax + shipping - discount
        assert isinstance(gross, int)


def testBuildSplitManifestSumConservation() -> None:
    """Verifies split manifest amount conservation and merchant net calculation."""
    mSigner = Ed25519Signer(generateKeyPair()[0])
    taxable, tax, shipping = 100000, 18000, 5000
    total = taxable + tax + shipping

    item = CartItemSchema(
        skuId="SKU-TEST", quantity=1, unitPricePaise=taxable,
        hsnCode="84713010", gstRatePercent=18, lineTotalPaise=taxable,
    )
    cartM = createSignedCartMandate(
        cartId="M-C-TEST-SPLIT", merchantSigner=mSigner, merchantGstin="29AAAAA0000A1ZY",
        merchantStateCode="29", buyerDeliveryPincode="560001", buyerDeliveryStateCode="29",
        items=[item], taxableSubtotalPaise=taxable,
        taxBreakdown=TaxBreakdownSchema(cgstPaise=9000, sgstPaise=9000, igstPaise=0, totalTaxPaise=tax),
        shippingPaise=shipping, discountPaise=0, totalPaise=total,
        inventoryLockToken="lock_tok", inventoryLockExpiresAt=2000000000,
    )
    manifest = buildSplitManifest(
        cartMandate=cartM, merchantAccount="acc_merchant_xyz",
        protocolFeeAccount="acc_protocol_fees", protocolFeePaise=50,
        logisticsAccount="acc_logistics_delhivery",
    )
    assert manifest.merchantAmountPaise == total - 50 - shipping
    assert manifest.protocolFeePaise == 50
    assert manifest.logisticsAmountPaise == shipping
    assert manifest.totalPaise == total
    assert manifest.merchantAmountPaise + manifest.protocolFeePaise + manifest.logisticsAmountPaise == total
