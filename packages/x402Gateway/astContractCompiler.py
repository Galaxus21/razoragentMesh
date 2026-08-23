"""AST Contract Compiler for compiling negotiated commercial terms into frozen schemas."""

from pydantic import BaseModel, ConfigDict, Field

from razoragentMesh.packages.mandateEngine.arithmeticEnclave import (
    computeCartSettlementTotal,
    computeGstBreakdown,
    computeLineItemTotal,
    validateIntegerPaise,
)
from razoragentMesh.packages.mandateEngine.jcsCanonicalizer import (
    canonicalizeJson,
    computeSha256Digest,
)
from razoragentMesh.packages.x402Gateway.gatewayConstants import defaultGstRatePercent


class CommercialContractAst(BaseModel):
    """Immutable Commercial Contract AST representing agreed negotiation terms."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    skuId: str = Field(min_length=1)
    quantity: int = Field(gt=0)
    agreedUnitPricePaise: int = Field(gt=0)
    taxableSubtotalPaise: int = Field(gt=0)
    totalTaxPaise: int = Field(ge=0)
    totalGrossPaise: int = Field(gt=0)
    settlementTurns: int = Field(ge=1)
    buyerAgentDid: str = Field(min_length=1)
    merchantDid: str = Field(min_length=1)
    contractTimestamp: int = Field(gt=0)


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
    gross = computeCartSettlementTotal(taxable, gst["totalTaxPaise"])

    ast = CommercialContractAst(
        skuId=skuId,
        quantity=quantity,
        agreedUnitPricePaise=agreedUnitPrice,
        taxableSubtotalPaise=taxable,
        totalTaxPaise=gst["totalTaxPaise"],
        totalGrossPaise=gross,
        settlementTurns=turns,
        buyerAgentDid=buyerDid,
        merchantDid=merchantDid,
        contractTimestamp=timestamp,
    )
    canonicalBytes = canonicalizeJson(ast)
    astHash = computeSha256Digest(canonicalBytes)
    return ast, astHash
