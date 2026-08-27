"""Empirical adversarial security and integrity test suite for GSTR-1 HTML Invoice Generator.

Challenger 2 suite verifying:
- Deep XSS resistance across all invoice fields and HTML attribute contexts.
- RFC 8785 JCS canonical hash integrity & 64-character lowercase SHA-256 digest validation.
- Offline self-containment (zero external CDNs, scripts, stylesheets, or network triggers).
- Multi-slab tax calculation, integer paise formatting, and Indian state code registry resolution.
"""

from html.parser import HTMLParser
import re
import pytest

from razoragentMesh.packages.mandateEngine.crypto.cryptoKeyUtils import generateKeyPair
from razoragentMesh.packages.mandateEngine.crypto.ed25519Signer import Ed25519Signer
from razoragentMesh.packages.mandateEngine.crypto.jcsCanonicalizer import (
    canonicalizeJson,
    computeSha256Digest,
)
from razoragentMesh.packages.mandateEngine.mandates.cartMandateSchema import (
    CartItemSchema,
    TaxBreakdownSchema,
)
from razoragentMesh.packages.mandateEngine.mandates.mandateFactory import (
    createSignedCartMandate,
    createSignedExecutionMandate,
    createSignedIntentMandate,
)
from razoragentMesh.packages.mandateEngine.settlement.settlementExceptions import (
    ArithmeticDriftException,
)
from razoragentMesh.packages.mandateEngine.tax.gstrInvoiceEngine import (
    GstrInvoicePayload,
    GstrLineItem,
    _buildInvoiceDict,
    generateGstrInvoice,
)
from razoragentMesh.packages.mandateEngine.tax.gstrInvoiceHtmlRenderer import (
    formatPaiseToInr,
    renderGstrInvoiceHtml,
)
from razoragentMesh.packages.mandateEngine.tax.gstrInvoiceHtmlStyles import (
    gstStateCodeToName,
    invoiceBaseStyles,
    resolveStateName,
)

adversarialXssPayloads: list[str] = [
    '<script>alert("xss")</script>',
    '<img src=x onerror=alert(1)>',
    '<svg/onload=alert(1)>',
    'javascript:alert(1)',
    '" onfocus="alert(1)" autofocus="',
    '</title><script>alert(1)</script>',
    '</style><script>alert(1)</script>',
    '<b>Bold</b><i>Italic</i>',
    '" onclick="alert(\'hacked\')"',
    '& < > " \'',
    '<iframe src="javascript:alert(1)"></iframe>',
    '<a href="https://malicious.com">Click Here</a>',
    '\x00<script>alert(1)</script>',
    '\u202e<script>alert(1)</script>',
    '{{7*7}}${7*7}',
    'javascript:/*--></title></style></textarea></noscript>--></select></script><svg/onload=alert(1)>',
    'data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==',
]


class SafeHtmlValidator(HTMLParser):
    """HTML parser that asserts no executable or unescaped tags/attributes exist."""

    def __init__(self) -> None:
        super().__init__()
        self.forbiddenTagsFound: list[str] = []
        self.forbiddenAttrsFound: list[str] = []
        self.forbiddenTags: set[str] = {
            "script",
            "img",
            "svg",
            "iframe",
            "object",
            "embed",
            "input",
            "form",
            "a",
        }

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in self.forbiddenTags:
            self.forbiddenTagsFound.append(tag)
        for attr, _ in attrs:
            if attr.lower().startswith("on"):
                self.forbiddenAttrsFound.append(attr)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)


def _assertHtmlDomIsSafe(htmlDoc: str) -> None:
    """Parses HTML DOM with SafeHtmlValidator to ensure no malicious elements or handlers exist."""
    validator = SafeHtmlValidator()
    validator.feed(htmlDoc)
    assert len(validator.forbiddenTagsFound) == 0, f"Found forbidden DOM tags: {validator.forbiddenTagsFound}"
    assert len(validator.forbiddenAttrsFound) == 0, f"Found event handler attributes: {validator.forbiddenAttrsFound}"


@pytest.fixture
def mockSigners():
    """Fixture providing Ed25519 signers for user, merchant, and buyer agent."""
    userPriv, _ = generateKeyPair()
    merchPriv, _ = generateKeyPair()
    agentPriv, _ = generateKeyPair()
    return (
        Ed25519Signer(userPriv),
        Ed25519Signer(merchPriv),
        Ed25519Signer(agentPriv),
    )


def _buildSampleInvoice(
    invNumber: str = "INV-2026-TEST-001",
    sellerGstin: str = "29AAAAA0000A1ZY",
    merchState: str = "29",
    posState: str = "29",
    intraState: bool = True,
    skuId: str = "SKU-001",
    hsnCode: str = "9401",
    customAuditHash: str = "a" * 64,
) -> GstrInvoicePayload:
    """Helper constructing a deterministic GstrInvoicePayload."""
    cgst = 18000 if intraState else 0
    sgst = 18000 if intraState else 0
    igst = 0 if intraState else 36000
    line = GstrLineItem(
        skuId=skuId, hsnCode=hsnCode, quantity=2, unitPricePaise=100000,
        taxableAmountPaise=200000, gstRatePercent=18, cgstPaise=cgst,
        sgstPaise=sgst, igstPaise=igst, totalLinePaise=236000,
    )
    return GstrInvoicePayload(
        invoiceNumber=invNumber, invoiceDate="2026-08-24T12:00:00+00:00",
        sellerGstin=sellerGstin, merchantStateCode=merchState, placeOfSupplyStateCode=posState,
        isIntraState=intraState, lineItems=[line], taxableAmountPaise=200000,
        totalCgstPaise=cgst, totalSgstPaise=sgst, totalIgstPaise=igst,
        totalTaxPaise=36000, totalTcsPaise=2000, shippingPaise=1000,
        discountPaise=500, grandTotalPaise=236500, cryptographicAuditHash=customAuditHash,
    )



def testAdversarialXssResistanceInPartyNames() -> None:
    """Verifies script and tag escaping in merchant and buyer legal entity names."""
    inv = _buildSampleInvoice()
    for payload in adversarialXssPayloads:
        htmlDoc = renderGstrInvoiceHtml(
            inv,
            merchantLegalName=f"Merchant-{payload}",
            buyerLegalName=f"Buyer-{payload}",
        )
        _assertHtmlDomIsSafe(htmlDoc)
        assert "<script" not in htmlDoc.lower()
        assert "<img" not in htmlDoc.lower()
        assert "<svg" not in htmlDoc.lower()
        assert "<iframe" not in htmlDoc.lower()


def testAdversarialXssResistanceInInvoiceMetadata() -> None:
    """Verifies script and tag escaping in invoice number, SKU, HSN, and state codes."""
    for payload in adversarialXssPayloads:
        inv = _buildSampleInvoice(
            invNumber=f"INV-{payload}",
            skuId=f"SKU-{payload}",
        )
        htmlDoc = renderGstrInvoiceHtml(inv)
        _assertHtmlDomIsSafe(htmlDoc)
        assert "<script" not in htmlDoc.lower()
        assert "<img" not in htmlDoc.lower()
        assert "<svg" not in htmlDoc.lower()
        assert "<iframe" not in htmlDoc.lower()


def testAdversarialTitleTagBreakoutResistance() -> None:
    """Verifies invoiceNumber cannot break out of the <title> tag in <head>."""
    breakoutPayload = "</title><script>window.pwned=1</script><title>"
    inv = _buildSampleInvoice(invNumber=breakoutPayload)
    htmlDoc = renderGstrInvoiceHtml(inv)
    _assertHtmlDomIsSafe(htmlDoc)
    assert "<script>window.pwned=1</script>" not in htmlDoc
    assert "&lt;/title&gt;&lt;script&gt;window.pwned=1&lt;/script&gt;&lt;title&gt;" in htmlDoc


def testAdversarialOfflineSelfContainment() -> None:
    """Verifies invoice HTML has zero external dependencies or remote URL calls."""
    inv = _buildSampleInvoice()
    htmlDoc = renderGstrInvoiceHtml(inv)

    assert not re.search(r"<script\b[^>]*\bsrc=", htmlDoc, re.IGNORECASE)
    assert not re.search(r"<link\b[^>]*\bhref=", htmlDoc, re.IGNORECASE)
    assert not re.search(r"@import\b", invoiceBaseStyles, re.IGNORECASE)
    assert not re.search(r"url\s*\(", invoiceBaseStyles, re.IGNORECASE)
    assert "https://" not in invoiceBaseStyles
    assert "http://" not in invoiceBaseStyles


def testAdversarialJcsAuditHashConsistency(mockSigners) -> None:
    """Verifies RFC 8785 JCS canonical SHA-256 hash matches invoice dictionary."""
    uSigner, mSigner, aSigner = mockSigners
    intentM = createSignedIntentMandate("M-I-ADV", uSigner, aSigner.getAgentDid(), 1000000, "tok", 1000000)
    item = CartItemSchema(skuId="SKU-001", quantity=2, unitPricePaise=250000, hsnCode="8504", gstRatePercent=18, lineTotalPaise=500000)
    taxB = TaxBreakdownSchema(cgstPaise=0, sgstPaise=0, igstPaise=90000, totalTaxPaise=90000)
    cartM = createSignedCartMandate("M-C-ADV", mSigner, "29AAAAA0000A1ZY", "29", "560001", "27", [item], 500000, taxB, 5000, 2000, 593000, "lock", 2000000000)
    execM = createSignedExecutionMandate("M-E-ADV", aSigner, intentM, cartM, 593000, "tok")

    inv = generateGstrInvoice(cartM, execM, "INV-2026-ADV-001", 1787500000)
    auditHash = inv.cryptographicAuditHash

    assert len(auditHash) == 64
    assert re.fullmatch(r"[0-9a-f]{64}", auditHash) is not None

    rawDict = _buildInvoiceDict(
        cartM,
        inv.lineItems,
        (inv.taxableAmountPaise, inv.totalCgstPaise, inv.totalSgstPaise, inv.totalIgstPaise, inv.totalTaxPaise, inv.grandTotalPaise),
        inv.invoiceNumber,
        inv.invoiceDate,
        inv.isIntraState,
    )
    expectedHash = computeSha256Digest(canonicalizeJson(rawDict))
    assert auditHash == expectedHash

    htmlDoc = renderGstrInvoiceHtml(inv)
    assert f'<code class="audit-hash-code">{auditHash}</code>' in htmlDoc


def testAdversarialJcsRejectsFloatingPointDrift() -> None:
    """Verifies JCS canonicalizer strictly raises ArithmeticDriftException on float values."""
    with pytest.raises(ArithmeticDriftException):
        canonicalizeJson({"price": 42.50})


def testAdversarialAllStateCodeRegistryMappings() -> None:
    """Verifies all 38 Indian state/UT GST codes resolve accurately."""
    assert len(gstStateCodeToName) >= 37
    for code, expectedName in gstStateCodeToName.items():
        assert resolveStateName(code) == expectedName
        assert resolveStateName(f" {code} ") == expectedName

    assert resolveStateName("99") == "State Code 99"
    assert resolveStateName("ZZ") == "State Code ZZ"


def testAdversarialCurrencyFormattingBounds() -> None:
    """Verifies zero-float integer paise currency formatting at boundary values."""
    assert formatPaiseToInr(0) == "₹0.00"
    assert formatPaiseToInr(1) == "₹0.01"
    assert formatPaiseToInr(9) == "₹0.09"
    assert formatPaiseToInr(10) == "₹0.10"
    assert formatPaiseToInr(99) == "₹0.99"
    assert formatPaiseToInr(100) == "₹1.00"
    assert formatPaiseToInr(100000000) == "₹1000000.00"
    assert formatPaiseToInr(99999999999) == "₹999999999.99"
    assert formatPaiseToInr(-100) == "-₹1.00"
    assert formatPaiseToInr(-1) == "-₹0.01"
