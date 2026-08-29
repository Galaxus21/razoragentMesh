"""AST Contract Compiler for compiling negotiated commercial terms into frozen schemas."""

from ..constants.arithmeticUtils import (
    computeCartSettlementTotal,
    computeGstBreakdown,
    computeLineItemTotal,
    validateIntegerPaise,
)
from ..constants.negotiationConstants import defaultGstRatePercent
from ..schemas.contractAstSchema import CommercialContractAst
from .jcsSerializer import canonicalizeJson, computeSha256Digest


def compileCommercialContractAst(
    skuId: str,
    quantity: int,
    agreedUnitPrice: int,
    turns: int,
    buyerDid: str,
    merchantDid: str,
    timestamp: int,
    gstRate: int = defaultGstRatePercent,
    isIntraState: bool = True,
) -> tuple[CommercialContractAst, str]:
    """Compiles negotiated terms into immutable AST and computes canonical JCS SHA-256 hash."""
    validateIntegerPaise(agreedUnitPrice, "agreedUnitPrice")
    validateIntegerPaise(quantity, "quantity")
    validateIntegerPaise(turns, "turns")
    validateIntegerPaise(timestamp, "timestamp")

    taxable = computeLineItemTotal(agreedUnitPrice, quantity)
    gst = computeGstBreakdown(taxable, gstRate, isIntraState=isIntraState)
    gross = computeCartSettlementTotal(taxable, gst.totalTaxPaise)

    ast = CommercialContractAst(
        skuId=skuId,
        quantity=quantity,
        agreedUnitPricePaise=agreedUnitPrice,
        taxableSubtotalPaise=taxable,
        totalTaxPaise=gst.totalTaxPaise,
        totalGrossPaise=gross,
        settlementTurns=turns,
        buyerAgentDid=buyerDid,
        merchantDid=merchantDid,
        contractTimestamp=timestamp,
    )
    canonicalBytes = canonicalizeJson(ast)
    astHash = computeSha256Digest(canonicalBytes)
    return ast, astHash


__all__ = [
    "CommercialContractAst",
    "compileCommercialContractAst",
]
