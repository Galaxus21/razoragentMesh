"""GSTR-1 compliant tax invoice generation engine."""

from datetime import datetime, timezone
import time
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field

from razoragentMesh.packages.mandateEngine.arithmeticEnclave import (
    computeGstBreakdown,
    computeLineItemTotal,
    computeTcsWithholding,
)
from razoragentMesh.packages.mandateEngine.cartMandateSchema import CartMandate
from razoragentMesh.packages.mandateEngine.executionMandateSchema import ExecutionMandate
from razoragentMesh.packages.mandateEngine.jcsCanonicalizer import (
    canonicalizeJson,
    computeSha256Digest,
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
    """Immutable GSTR-1 tax invoice with cryptographic audit hash."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    invoiceNumber: str = Field(min_length=1)
    invoiceDate: str = Field(min_length=1)
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
    """Checks whether transaction is intra-state (same state code) or inter-state."""
    return merchantStateCode.strip() == buyerDeliveryStateCode.strip()


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

    for itm in cartMandate.items:
        lineTaxable = computeLineItemTotal(itm.unitPricePaise, itm.quantity)
        gst = computeGstBreakdown(lineTaxable, itm.gstRatePercent, intraState)
        items.append(
            GstrLineItem(
                skuId=itm.skuId,
                hsnCode=itm.hsnCode,
                quantity=itm.quantity,
                unitPricePaise=itm.unitPricePaise,
                taxableAmountPaise=lineTaxable,
                gstRatePercent=itm.gstRatePercent,
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
    cart: CartMandate,
    items: list[GstrLineItem],
    totals: tuple[int, int, int, int, int, int],
    num: str,
    dt: str,
    intra: bool,
) -> dict[str, Any]:
    """Builds raw dictionary for JCS canonical hashing."""
    taxable, cgst, sgst, igst, totalTax, grandTotal = totals
    tcs = computeTcsWithholding(taxable, intra)
    return {
        "discountPaise": cart.discountPaise,
        "grandTotalPaise": grandTotal,
        "invoiceDate": dt,
        "invoiceNumber": num,
        "isIntraState": intra,
        "lineItems": [item.model_dump() for item in items],
        "merchantStateCode": cart.merchantStateCode,
        "placeOfSupplyStateCode": cart.buyerDeliveryStateCode,
        "sellerGstin": cart.merchantGstin,
        "shippingPaise": cart.shippingPaise,
        "taxableAmountPaise": taxable,
        "totalCgstPaise": cgst,
        "totalIgstPaise": igst,
        "totalSgstPaise": sgst,
        "totalTaxPaise": totalTax,
        "totalTcsPaise": tcs["totalTcsPaise"],
    }


def generateGstrInvoice(
    cartMandate: CartMandate,
    executionMandate: ExecutionMandate,
    invoiceNumber: str,
    invoiceTimestamp: Optional[int] = None,
) -> GstrInvoicePayload:
    """Constructs GSTR-1 invoice payload with cryptographic JCS SHA-256 audit digest."""
    ts = invoiceTimestamp or int(time.time())
    isoDate = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    intra = isPlaceOfSupplyIntraState(cartMandate.merchantStateCode, cartMandate.buyerDeliveryStateCode)

    items, taxable, cgst, sgst, igst = _buildLineItemsAndTaxTotals(cartMandate, intra)
    totTax = cgst + sgst + igst
    grandTot = taxable + totTax + cartMandate.shippingPaise - cartMandate.discountPaise
    totals = (taxable, cgst, sgst, igst, totTax, grandTot)

    invDict = _buildInvoiceDict(cartMandate, items, totals, invoiceNumber, isoDate, intra)
    tcs = computeTcsWithholding(taxable, intra)
    auditHash = computeSha256Digest(canonicalizeJson(invDict))

    return GstrInvoicePayload(
        invoiceNumber=invoiceNumber,
        invoiceDate=isoDate,
        sellerGstin=cartMandate.merchantGstin,
        merchantStateCode=cartMandate.merchantStateCode,
        placeOfSupplyStateCode=cartMandate.buyerDeliveryStateCode,
        isIntraState=intra,
        lineItems=items,
        taxableAmountPaise=taxable,
        totalCgstPaise=cgst,
        totalSgstPaise=sgst,
        totalIgstPaise=igst,
        totalTaxPaise=totTax,
        totalTcsPaise=tcs["totalTcsPaise"],
        shippingPaise=cartMandate.shippingPaise,
        discountPaise=cartMandate.discountPaise,
        grandTotalPaise=grandTot,
        cryptographicAuditHash=auditHash,
    )
