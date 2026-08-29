"""Canonical tax fixtures and deterministic calculation helpers for testing."""

from dataclasses import dataclass
from typing import Dict, List, Sequence

from razoragentMesh.packages.mandateEngine.mandates.cartMandateSchema import (
    CartItemSchema,
)
from razoragentMesh.packages.mandateEngine.verification.arithmeticEnclave import (
    computeCartSettlementTotal,
    computeGstBreakdown,
    computeLineItemTotal,
    computeTcsWithholding,
)

# Constants
defaultSlabList: tuple[int, ...] = (0, 5, 12, 18, 28)
defaultUnitPricePaise: int = 100000
defaultHsnPrefix: str = "84"


@dataclass(frozen=True)
class TaxScenario:
    """Canonical statutory tax test scenario with expected integer values."""

    taxablePaise: int
    gstRatePercent: int
    isIntraState: bool
    expectedCgstPaise: int
    expectedSgstPaise: int
    expectedIgstPaise: int
    expectedTotalTaxPaise: int
    expectedTcsPaise: int


def getCanonicalOddPaiseScenarios() -> List[TaxScenario]:
    """Returns statutory test scenarios for odd paise, floor division, and TCS."""
    rawScenarios = [
        (101, 5, True, 2, 2, 0, 4, 0),
        (33333, 5, True, 833, 833, 0, 1666, 332),
        (77777, 18, False, 0, 0, 13999, 13999, 777),
        (99999, 18, True, 8999, 8999, 0, 17998, 998),
        (100000, 18, True, 9000, 9000, 0, 18000, 1000),
        (100000, 18, False, 0, 0, 18000, 18000, 1000),
    ]
    return [
        TaxScenario(
            taxablePaise=t, gstRatePercent=r, isIntraState=intra,
            expectedCgstPaise=cg, expectedSgstPaise=sg, expectedIgstPaise=ig,
            expectedTotalTaxPaise=tot, expectedTcsPaise=tcs,
        )
        for t, r, intra, cg, sg, ig, tot, tcs in rawScenarios
    ]


def generateMultiSlabLineItems(
    slabs: Sequence[int] = defaultSlabList,
    unitPriceMultiplier: int = 100000,
) -> List[CartItemSchema]:
    """Generates standardized cart line items spanning given GST tax rate slabs."""
    items: List[CartItemSchema] = []
    for idx, rate in enumerate(slabs):
        quantity = idx + 1
        unitPrice = (idx + 1) * unitPriceMultiplier if idx > 0 else unitPriceMultiplier
        lineTotal = computeLineItemTotal(unitPrice, quantity)
        items.append(
            CartItemSchema(
                skuId=f"SKU-GST-SLAB-{rate}",
                quantity=quantity,
                unitPricePaise=unitPrice,
                hsnCode=f"{defaultHsnPrefix}{rate:02d}00",
                gstRatePercent=rate,
                lineTotalPaise=lineTotal,
            )
        )
    return items


def computeExpectedSettlementTotals(
    items: List[CartItemSchema],
    isIntraState: bool,
    shippingPaise: int = 0,
    discountPaise: int = 0,
) -> Dict[str, int]:
    """Computes statutory tax and settlement totals across cart line items."""
    taxableSubtotal = sum(i.lineTotalPaise for i in items)
    totalCgst, totalSgst, totalIgst = 0, 0, 0
    for item in items:
        gst = computeGstBreakdown(item.lineTotalPaise, item.gstRatePercent, isIntraState)
        totalCgst += gst.cgstPaise
        totalSgst += gst.sgstPaise
        totalIgst += gst.igstPaise

    totalTax = totalCgst + totalSgst + totalIgst
    tcs = computeTcsWithholding(taxableSubtotal, isIntraState)
    grossTotal = computeCartSettlementTotal(taxableSubtotal, totalTax, shippingPaise, discountPaise)
    return {
        "taxableSubtotalPaise": taxableSubtotal, "totalCgstPaise": totalCgst,
        "totalSgstPaise": totalSgst, "totalIgstPaise": totalIgst, "totalTaxPaise": totalTax,
        "tcsCgstPaise": tcs["tcsCgstPaise"], "tcsSgstPaise": tcs["tcsSgstPaise"],
        "tcsIgstPaise": tcs["tcsIgstPaise"], "totalTcsPaise": tcs["totalTcsPaise"],
        "shippingPaise": shippingPaise, "discountPaise": discountPaise, "grossTotalPaise": grossTotal,
    }

