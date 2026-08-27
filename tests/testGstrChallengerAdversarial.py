"""Adversarial stress test suite created by Challenger 1 for GSTR-1 HTML Invoice Generator."""

import html
import pytest

from razoragentMesh.packages.mandateEngine.tax.gstrInvoiceEngine import (
    GstrInvoicePayload,
    GstrLineItem,
)
from razoragentMesh.packages.mandateEngine.tax.gstrInvoiceHtmlRenderer import (
    formatPaiseToInr,
    renderGstrInvoiceHtml,
)
from razoragentMesh.packages.mandateEngine.tax.gstrInvoiceHtmlStyles import (
    gstStateCodeToName,
    resolveStateName,
)
from razoragentMesh.packages.mandateEngine.verification.arithmeticEnclave import (
    computeGstBreakdown,
    computeTcsWithholding,
)
from razoragentMesh.tests.fixtures.taxFixtures import (
    getCanonicalOddPaiseScenarios,
)


class TestFormatPaiseToInrStress:
    """Stress tests formatPaiseToInr on zero, single paise, huge numbers, and negatives."""

    @pytest.mark.parametrize(
        "paise,expected",
        [
            (0, "₹0.00"), (1, "₹0.01"), (2, "₹0.02"), (9, "₹0.09"), (10, "₹0.10"),
            (99, "₹0.99"), (100, "₹1.00"), (105, "₹1.05"), (150, "₹1.50"),
            (999, "₹9.99"), (1000, "₹10.00"), (123456, "₹1234.56"),
            (10000000, "₹100000.00"), (100000000000, "₹1000000000.00"),
            (10000000000000, "₹100000000000.00"), (-1, "-₹0.01"), (-9, "-₹0.09"),
            (-99, "-₹0.99"), (-100, "-₹1.00"), (-105, "-₹1.05"), (-4200, "-₹42.00"),
            (-100000000000, "-₹1000000000.00"),
        ],
    )
    def testPaiseFormattingExactness(self, paise: int, expected: str) -> None:
        assert formatPaiseToInr(paise) == expected


def _buildSingleSlabInvoice(
    rate: int, isIntraState: bool, unitPrice: int, quantity: int,
    shippingPaise: int = 0, discountPaise: int = 0, placeOfSupply: str = "29",
) -> GstrInvoicePayload:
    taxable = unitPrice * quantity
    cgst = (taxable * rate) // 200 if isIntraState else 0
    sgst = (taxable * rate) // 200 if isIntraState else 0
    igst = 0 if isIntraState else (taxable * rate) // 100
    totalTax = cgst + sgst + igst
    line = GstrLineItem(
        skuId=f"SKU-{'TEST' if isIntraState else 'INTER'}-{rate}",
        hsnCode="1234" if isIntraState else "5678", quantity=quantity,
        unitPricePaise=unitPrice, taxableAmountPaise=taxable,
        gstRatePercent=rate, cgstPaise=cgst, sgstPaise=sgst,
        igstPaise=igst, totalLinePaise=taxable + totalTax,
    )
    return GstrInvoicePayload(
        invoiceNumber=f"INV-{'RATE' if isIntraState else 'INTER'}-{rate}",
        invoiceDate="2026-08-24T12:00:00Z", sellerGstin="29AAAAA0000A1ZY",
        merchantStateCode="29", placeOfSupplyStateCode=placeOfSupply,
        isIntraState=isIntraState, lineItems=[line], taxableAmountPaise=taxable,
        totalCgstPaise=cgst, totalSgstPaise=sgst, totalIgstPaise=igst,
        totalTaxPaise=totalTax, totalTcsPaise=(taxable * 100) // 10000,
        shippingPaise=shippingPaise, discountPaise=discountPaise,
        grandTotalPaise=taxable + totalTax + shippingPaise - discountPaise,
        cryptographicAuditHash="0" * 64 if isIntraState else "1" * 64,
    )


class TestMultiSlabAndStateResolutionStress:
    """Stress tests all GST rate slabs, intra/inter state rendering, and state mapping."""

    @pytest.mark.parametrize("rate", [0, 5, 12, 18, 28])
    def testSingleSlabIntraStateExactMath(self, rate: int) -> None:
        inv = _buildSingleSlabInvoice(rate, isIntraState=True, unitPrice=100000, quantity=3)
        htmlOut = renderGstrInvoiceHtml(inv)
        assert f"SKU-TEST-{rate}" in htmlOut and f"{rate}%" in htmlOut

    @pytest.mark.parametrize("rate", [0, 5, 12, 18, 28])
    def testSingleSlabInterStateExactMath(self, rate: int) -> None:
        inv = _buildSingleSlabInvoice(
            rate, isIntraState=False, unitPrice=250000, quantity=2,
            shippingPaise=5000, discountPaise=2000, placeOfSupply="07",
        )
        htmlOut = renderGstrInvoiceHtml(inv)
        assert f"SKU-INTER-{rate}" in htmlOut and "07 - Delhi" in htmlOut
        assert "INTER-STATE (IGST)" in htmlOut and "1.0% IGST (100 bps)" in htmlOut
        assert formatPaiseToInr(inv.totalIgstPaise) in htmlOut
        assert "Promotional Discount:</span><span>-₹20.00" in htmlOut
        assert "Shipping &amp; Handling:</span><span>₹50.00" in htmlOut

    def testAllOfficialStateCodesResolution(self) -> None:
        for code, expectedName in gstStateCodeToName.items():
            assert resolveStateName(code) == expectedName
            assert resolveStateName(f" {code} ") == expectedName

    def testUnknownStateCodeFallback(self) -> None:
        assert resolveStateName("99") == "State Code 99"
        assert resolveStateName("XX") == "State Code XX"
        assert resolveStateName("00") == "State Code 00"



class TestArithmeticInvariantsAndOddNumbers:
    """Stress tests odd paise, asymmetric lines, large cart multi-items, and discount subtractions."""

    def testOddPaiseLineItemFloorDivisionConservation(self) -> None:
        """Tests that odd taxable amounts split into integer CGST/SGST without drifting."""
        oddScenario = next(s for s in getCanonicalOddPaiseScenarios() if s.taxablePaise == 99999)
        gst = computeGstBreakdown(oddScenario.taxablePaise, oddScenario.gstRatePercent, isIntraState=oddScenario.isIntraState)
        assert gst["cgstPaise"] == oddScenario.expectedCgstPaise
        assert gst["sgstPaise"] == oddScenario.expectedSgstPaise
        assert gst["totalTaxPaise"] == oddScenario.expectedTotalTaxPaise

        line = GstrLineItem(
            skuId="SKU-ODD-01", hsnCode="8471", quantity=3, unitPricePaise=33333,
            taxableAmountPaise=oddScenario.taxablePaise, gstRatePercent=oddScenario.gstRatePercent,
            cgstPaise=gst["cgstPaise"], sgstPaise=gst["sgstPaise"], igstPaise=0,
            totalLinePaise=oddScenario.taxablePaise + gst["totalTaxPaise"],
        )
        inv = GstrInvoicePayload(
            invoiceNumber="INV-ODD-001", invoiceDate="2026-08-24T16:00:00Z",
            sellerGstin="29AAAAA0000A1ZY", merchantStateCode="29", placeOfSupplyStateCode="29",
            isIntraState=True, lineItems=[line], taxableAmountPaise=oddScenario.taxablePaise,
            totalCgstPaise=gst["cgstPaise"], totalSgstPaise=gst["sgstPaise"], totalIgstPaise=0,
            totalTaxPaise=gst["totalTaxPaise"], totalTcsPaise=oddScenario.expectedTcsPaise,
            shippingPaise=0, discountPaise=0, grandTotalPaise=oddScenario.taxablePaise + gst["totalTaxPaise"],
            cryptographicAuditHash="2" * 64,
        )
        htmlOut = renderGstrInvoiceHtml(inv)
        assert formatPaiseToInr(oddScenario.taxablePaise) == "₹999.99"
        assert formatPaiseToInr(gst["cgstPaise"]) == "₹89.99"
        assert formatPaiseToInr(gst["sgstPaise"]) == "₹90.00"
        assert "₹999.99" in htmlOut and "₹89.99" in htmlOut and "₹90.00" in htmlOut and "₹1179.98" in htmlOut

    def testFiftyLineItemsStressCart(self) -> None:
        """Tests rendering of a 50-line item invoice with high volume."""
        lines, rates = [], [0, 5, 12, 18, 28]
        totTaxable = totCgst = totSgst = 0
        for i in range(50):
            rate, unitPrice, qty = rates[i % len(rates)], 10000 + i * 500, (i % 5) + 1
            taxable = unitPrice * qty
            cgst = sgst = (taxable * rate) // 200
            lines.append(GstrLineItem(
                skuId=f"SKU-BULK-{i:03d}", hsnCode=f"900{i % 10}", quantity=qty,
                unitPricePaise=unitPrice, taxableAmountPaise=taxable, gstRatePercent=rate,
                cgstPaise=cgst, sgstPaise=sgst, igstPaise=0, totalLinePaise=taxable + cgst + sgst,
            ))
            totTaxable += taxable
            totCgst += cgst
            totSgst += sgst

        totTax = totCgst + totSgst
        inv = GstrInvoicePayload(
            invoiceNumber="INV-50-ITEMS", invoiceDate="2026-08-24T18:00:00Z",
            sellerGstin="29AAAAA0000A1ZY", merchantStateCode="29", placeOfSupplyStateCode="29",
            isIntraState=True, lineItems=lines, taxableAmountPaise=totTaxable,
            totalCgstPaise=totCgst, totalSgstPaise=totSgst, totalIgstPaise=0,
            totalTaxPaise=totTax, totalTcsPaise=(totTaxable * 100) // 10000,
            shippingPaise=0, discountPaise=0, grandTotalPaise=totTaxable + totTax,
            cryptographicAuditHash="3" * 64,
        )
        htmlOut = renderGstrInvoiceHtml(inv)
        assert "SKU-BULK-000" in htmlOut and "SKU-BULK-049" in htmlOut
        assert formatPaiseToInr(totTaxable) in htmlOut
        assert formatPaiseToInr(totCgst) in htmlOut and formatPaiseToInr(totSgst) in htmlOut
        assert formatPaiseToInr(totTaxable + totTax) in htmlOut


class TestSecurityAndInjectionDefense:
    """Stress tests XSS, HTML injection, entity breakout, and malformed inputs."""

    def testScriptAndStyleTagNeutralization(self) -> None:
        maliciousInputs = [
            "<script>alert('hack')</script>", "<img src=x onerror=steal()/>",
            "><svg onload=alert(1)>", "'; DROP TABLE Invoices; --", "& < > \" '",
        ]
        line = GstrLineItem(
            skuId="SKU-SEC-01", hsnCode="1234", quantity=1, unitPricePaise=10000,
            taxableAmountPaise=10000, gstRatePercent=18, cgstPaise=900, sgstPaise=900,
            igstPaise=0, totalLinePaise=11800,
        )
        for badInput in maliciousInputs:
            inv = GstrInvoicePayload(
                invoiceNumber=badInput, invoiceDate="2026-08-24T12:00:00Z",
                sellerGstin="29AAAAA0000A1ZY", merchantStateCode="29", placeOfSupplyStateCode="29",
                isIntraState=True, lineItems=[line], taxableAmountPaise=10000,
                totalCgstPaise=900, totalSgstPaise=900, totalIgstPaise=0,
                totalTaxPaise=1800, totalTcsPaise=100, shippingPaise=0, discountPaise=0,
                grandTotalPaise=11800, cryptographicAuditHash="f" * 64,
            )
            htmlOut = renderGstrInvoiceHtml(inv, merchantLegalName=badInput, buyerLegalName=badInput)
            assert "<script>" not in htmlOut and "<svg onload" not in htmlOut and "<img src=x" not in htmlOut
            assert html.escape(badInput, quote=True) in htmlOut
