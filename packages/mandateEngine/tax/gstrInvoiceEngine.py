"""GSTR-1 compliant tax invoice generation engine."""

from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import TYPE_CHECKING, Any, Optional
from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from ..mandates.cartMandateSchema import CartMandate
    from ..mandates.executionMandateSchema import ExecutionMandate

from ..crypto.jcsCanonicalizer import (
    canonicalizeJson,
    computeSha256Digest,
)
from ..verification.arithmeticEnclave import (
    computeGstBreakdown,
    computeLineItemTotal,
    computeTcsWithholding,
)


class GstrLineItem(BaseModel):
    """Itemized invoice line item compliant with GST Rule 46."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    skuId: str = Field(min_length=1)
    hsnCode: str = Field(pattern=r"^[0-9]{4,8}$")
    quantity: int = Field(gt=0)
    unitPricePaise: int = Field(gt=0)
    taxableAmountPaise: int = Field(gt=0)
    gstRatePercent: int = Field(ge=0, le=28)
    cgstPaise: int = Field(ge=0)
    sgstPaise: int = Field(ge=0)
    igstPaise: int = Field(ge=0)
    totalLinePaise: int = Field(gt=0)


class GstrInvoicePayload(BaseModel):
    """GSTR-1 compliant invoice payload with cryptographic audit hash."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    invoiceNumber: str = Field(min_length=1)
    invoiceDate: str = Field(min_length=10)
    sellerGstin: str = Field(min_length=15, max_length=15)
    merchantStateCode: str = Field(min_length=2, max_length=2)
    placeOfSupplyStateCode: str = Field(min_length=2, max_length=2)
    isIntraState: bool
    lineItems: list[GstrLineItem] = Field(min_length=1)
    taxableAmountPaise: int = Field(gt=0)
    totalCgstPaise: int = Field(ge=0)
    totalSgstPaise: int = Field(ge=0)
    totalIgstPaise: int = Field(ge=0)
    totalTaxPaise: int = Field(ge=0)
    totalTcsPaise: int = Field(ge=0)
    shippingPaise: int = Field(ge=0)
    discountPaise: int = Field(ge=0)
    grandTotalPaise: int = Field(gt=0)
    cryptographicAuditHash: str = Field(min_length=64, max_length=64)


def isPlaceOfSupplyIntraState(merchantStateCode: str, buyerDeliveryStateCode: str) -> bool:
    """Determines whether transaction is intra-state (CGST+SGST) or inter-state (IGST)."""
    return merchantStateCode.strip() == buyerDeliveryStateCode.strip()


def generateGstrInvoice(
    cartMandate: CartMandate,
    executionMandate: Optional[ExecutionMandate] = None,
    invoiceNumberPrefix: str = "INV",
    timestamp: Optional[int] = None,
    *,
    invoiceTimestamp: Optional[int] = None,
    invoiceNumber: Optional[str] = None,
) -> GstrInvoicePayload:
    """Constructs GSTR-1 compliant invoice and calculates cryptographically canonical SHA-256."""
    ts = invoiceTimestamp if invoiceTimestamp is not None else (timestamp or int(time.time()))
    isoDate = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
    invNum = invoiceNumber if invoiceNumber is not None else f"{invoiceNumberPrefix}-{ts}"
    intraState = isPlaceOfSupplyIntraState(cartMandate.merchantStateCode, cartMandate.buyerDeliveryStateCode)

    items, taxable, cgst, sgst, igst = _buildLineItemsAndTaxTotals(cartMandate, intraState)
    totalTax = cgst + sgst + igst
    grandTotal = taxable + totalTax + cartMandate.shippingPaise - cartMandate.discountPaise
    totals = (taxable, cgst, sgst, igst, totalTax, grandTotal)

    invoiceDict = _buildInvoiceDict(cartMandate, items, totals, invNum, isoDate, intraState)
    tcs = computeTcsWithholding(taxable, intraState)
    auditHash = computeSha256Digest(canonicalizeJson(invoiceDict))

    return GstrInvoicePayload(
        invoiceNumber=invNum, invoiceDate=isoDate, sellerGstin=cartMandate.merchantGstin,
        merchantStateCode=cartMandate.merchantStateCode, placeOfSupplyStateCode=cartMandate.buyerDeliveryStateCode,
        isIntraState=intraState, lineItems=items, taxableAmountPaise=taxable,
        totalCgstPaise=cgst, totalSgstPaise=sgst, totalIgstPaise=igst, totalTaxPaise=totalTax,
        totalTcsPaise=tcs["totalTcsPaise"], shippingPaise=cartMandate.shippingPaise,
        discountPaise=cartMandate.discountPaise, grandTotalPaise=grandTotal,
        cryptographicAuditHash=auditHash,
    )


def _buildLineItemsAndTaxTotals(
    cartMandate: CartMandate,
    intraState: bool,
) -> tuple[list[GstrLineItem], int, int, int, int]:
    """Computes itemized line tax records and aggregated tax sums."""
    items: list[GstrLineItem] = []
    accumTaxable = 0
    accumCgst = 0
    accumSgst = 0
    accumIgst = 0

    for invoiceItem in cartMandate.items:
        lineTaxable = computeLineItemTotal(invoiceItem.unitPricePaise, invoiceItem.quantity)
        gst = computeGstBreakdown(lineTaxable, invoiceItem.gstRatePercent, intraState)
        items.append(
            GstrLineItem(
                skuId=invoiceItem.skuId,
                hsnCode=invoiceItem.hsnCode,
                quantity=invoiceItem.quantity,
                unitPricePaise=invoiceItem.unitPricePaise,
                taxableAmountPaise=lineTaxable,
                gstRatePercent=invoiceItem.gstRatePercent,
                cgstPaise=gst["cgstPaise"],
                sgstPaise=gst["sgstPaise"],
                igstPaise=gst["igstPaise"],
                totalLinePaise=lineTaxable + gst["totalTaxPaise"],
            )
        )
        accumTaxable += lineTaxable
        accumCgst += gst["cgstPaise"]
        accumSgst += gst["sgstPaise"]
        accumIgst += gst["igstPaise"]

    return items, accumTaxable, accumCgst, accumSgst, accumIgst


def _buildInvoiceDict(
    cartMandate: Optional[CartMandate] = None,
    items: Optional[list[GstrLineItem]] = None,
    totals: Optional[tuple[int, int, int, int, int, int]] = None,
    invoiceNumber: Optional[str] = None,
    invoiceDate: Optional[str] = None,
    isIntraState: Optional[bool] = None,
    *,
    cart: Optional[CartMandate] = None,
    num: Optional[str] = None,
    dt: Optional[str] = None,
    intra: Optional[bool] = None,
) -> dict[str, Any]:
    targetCart = cartMandate or cart
    targetItems = items if items is not None else []
    targetTotals = totals or (0, 0, 0, 0, 0, 0)
    targetNum = invoiceNumber or (num or "")
    targetDate = invoiceDate or (dt or "")
    targetIntra = isIntraState if isIntraState is not None else (intra if intra is not None else True)

    taxable, cgst, sgst, igst, totalTax, grandTotal = targetTotals
    tcsWithholding = computeTcsWithholding(taxable, targetIntra)
    return {
        "discountPaise": targetCart.discountPaise if targetCart else 0,
        "grandTotalPaise": grandTotal,
        "invoiceDate": targetDate,
        "invoiceNumber": targetNum,
        "isIntraState": targetIntra,
        "lineItems": [item.model_dump() for item in targetItems],
        "merchantStateCode": targetCart.merchantStateCode if targetCart else "29",
        "placeOfSupplyStateCode": targetCart.buyerDeliveryStateCode if targetCart else "29",
        "sellerGstin": targetCart.merchantGstin if targetCart else "",
        "shippingPaise": targetCart.shippingPaise if targetCart else 0,
        "taxableAmountPaise": taxable,
        "totalCgstPaise": cgst,
        "totalIgstPaise": igst,
        "totalSgstPaise": sgst,
        "totalTaxPaise": totalTax,
        "totalTcsPaise": tcsWithholding["totalTcsPaise"],
    }


__all__ = [
    "GstrInvoicePayload",
    "GstrLineItem",
    "generateGstrInvoice",
    "isPlaceOfSupplyIntraState",
]
