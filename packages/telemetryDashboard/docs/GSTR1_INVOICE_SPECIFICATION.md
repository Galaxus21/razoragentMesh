# 🧾 Statutory GSTR-1 Tax Invoice Specification & Deterministic Integer Tax Engine

---

## 1. Regulatory Invoicing Mandate & Statutory Framework

Under the Indian Goods and Services Tax (GST) regime, autonomous multi-agent commerce must produce non-repudiable, statutory tax invoices that comply with all applicable legal standards governing electronic invoicing and digital marketplace transactions.

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                INDIAN GST STATUTORY COMPLIANCE ARCHITECTURE                      │
│                                                                                                  │
│   ┌────────────────────────────────┐                 ┌───────────────────────────────────────┐   │
│   │     Section 31 (CGST Act)      │                 │         Rule 46 (CGST Rules)          │   │
│   │   Mandate to issue Tax Invoice │                 │  16 Mandatory Invoice Particulars     │   │
│   └───────────────┬────────────────┘                 └───────────────────┬───────────────────┘   │
│                   │                                                      │                       │
│                   └──────────────────────────┬───────────────────────────┘                       │
│                                              ▼                                                   │
│                        ┌───────────────────────────────────────────┐                             │
│                        │    GstrInvoiceEngine & HTML Renderer      │                             │
│                        │  - Pure integer paise math (INV-01)       │                             │
│                        │  - Deterministic floor tax splits (INV-02)│                             │
│                        │  - Section 52 TCS withholding breakdown   │                             │
│                        │  - Canonical JCS SHA-256 audit stamp      │                             │
│                        └─────────────────────┬─────────────────────┘                             │
│                                              │                                                   │
│                   ┌──────────────────────────┴───────────────────────────┐                       │
│                   ▼                                                      ▼                       │
│   ┌────────────────────────────────┐                 ┌───────────────────────────────────────┐   │
│   │   Print-Ready A4 HTML Invoice  │                 │    Canonical RFC 8785 JSON Digest     │   │
│   │   (Statutory PDF/Print Render) │                 │    (Non-Repudiable Cryptographic Audit│   │
│   └────────────────────────────────┘                 └───────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 1.1 Statutory Legal Basis

1. **Section 31 of Central Goods and Services Tax (CGST) Act, 2017:**
   Mandates that every registered taxable person supplying taxable goods or services must issue a tax invoice showing the description, quantity, value of goods, tax charged thereon, and other prescribed particulars.
2. **Rule 46 of CGST Rules, 2017 (Mandatory Invoice Particulars):**
   Requires sixteen essential particulars on every tax invoice, including:
   - Name, address, and Goods and Services Tax Identification Number (**GSTIN**) of the supplier.
   - A consecutive serial number not exceeding 16 characters containing alphabets, numerals, and special characters.
   - Date of invoice issuance.
   - Name, address, and GSTIN/Unique Identification Number (UIN) of the recipient.
   - Harmonized System of Nomenclature (**HSN**) code for goods or Accounting Code for services.
   - Description of goods or services.
   - Quantity of goods and unit of measurement.
   - Total taxable value of supply of goods or services taking into account any discount or abatement.
   - Rate of tax (Central GST, State GST, Integrated GST, or Cess).
   - Amount of tax charged in respect of taxable goods or services segregated by CGST, SGST, and IGST.
   - Place of supply along with the name of the State and its two-digit State Code.
   - Digital signature or electronic verification stamp of the supplier or authorized agent.
3. **Section 52 of CGST Act, 2017 (Tax Collection at Source / TCS):**
   Mandates that Electronic Commerce Operators (ECO) collect TCS at the rate of **1.00% (100 basis points)** on the net value of taxable supplies made through the platform:
   - **Intra-State Supplies:** 0.50% CGST (50 bps) + 0.50% SGST (50 bps).
   - **Inter-State Supplies:** 1.00% IGST (100 bps).

---

## 2. Deterministic Integer Paise Tax Engine

Financial calculations in RazorAgent Mesh are strictly isolated inside the **Arithmetic Enclave** (`mandateEngine/verification/arithmeticEnclave.py`). This enclave guarantees mathematical precision and prevents floating-point drift, fractional penny discrepancies, and non-deterministic rounding errors across multi-party settlements.

### 2.1 Invariant INV-01: Pure Integer Paise Arithmetic

- All financial values (prices, unit costs, discounts, shipping fees, tax components, and settlement splits) are represented strictly as **integer paise** ($1\text{ INR} = 100\text{ paise}$).
- The use of floating-point types (`float`, `double`) in any financial calculation path is strictly forbidden and triggers an immediate `ArithmeticDriftException`.

### 2.2 Invariant INV-02: Deterministic Statutory GST Calculation

GST is computed independently per itemized line item using statutory floor division. CGST and SGST are two separate levies, each charged at exactly half the combined rate, so both components are computed with the identical expression and are therefore always equal. The line total is defined as their sum, which makes penny conservation structural rather than something a rounding rule has to recover.

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                DETERMINISTIC TAX CALCULATION LOGIC                               │
│                                                                                                  │
│                               Place of Supply (POS) Check:                                       │
│                       merchantStateCode == buyerDeliveryStateCode                                │
│                                      /          \                                                │
│                                    YES           NO                                              │
│                                    /              \                                              │
│                         ┌─────────────┐        ┌─────────────┐                                   │
│                         │ INTRA-STATE │        │ INTER-STATE │                                   │
│                         └──────┬──────┘        └──────┬──────┘                                   │
│                                │                      │                                          │
│             ┌──────────────────┴───────────────┐      └────────────────────────────┐             │
│             ▼                                  ▼                                   ▼             │
│  CGST = SGST = ⌊ (Taxable × Rate) / 200 ⌋                               IGST = ⌊ (Taxable × Rate) / 100 ⌋
│  TotalTax = CGST + SGST,  IGST = 0                                      CGST = 0, SGST = 0       │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

#### Place of Supply Classification
$$\text{isIntraState} \iff \text{merchantStateCode} \equiv \text{buyerDeliveryStateCode}$$

#### Intra-State Formulation (CGST + SGST)
For supplies where the merchant and delivery location share the same two-digit GST state code:
$$\text{cgstPaise} = \text{sgstPaise} = \left\lfloor \frac{\text{taxableAmountPaise} \times \text{gstRatePercent}}{200} \right\rfloor$$
$$\text{totalTaxPaise} = \text{cgstPaise} + \text{sgstPaise}$$
$$\text{igstPaise} = 0$$

> **Statutory Equality Guarantee:** CGST and SGST are distinct levies each charged at half the combined rate, so they must be *equal*, not merely sum to the total. Both are computed from the identical expression, which makes that equality hold by construction for every rate — including odd slabs such as 5%, where deriving one component as the remainder of the other would produce an illegal asymmetric split (2% / 3% instead of 2.5% / 2.5%).
>
> **Exact Conservation Guarantee:** Because $\text{totalTaxPaise}$ is *defined* as $\text{cgstPaise} + \text{sgstPaise}$, the identity $\text{cgstPaise} + \text{sgstPaise} \equiv \text{totalTaxPaise}$ holds with zero drift by definition.
>
> The single division by $200$ (equivalently, by $20{,}000$ when the rate is expressed in basis points) is deliberate: halving the rate first and then flooring twice would discard up to one paise per line item and put this engine one paise out of step with the TypeScript MCP quoter.

#### Inter-State Formulation (IGST)
For supplies across differing state jurisdictions:
$$\text{cgstPaise} = 0$$
$$\text{sgstPaise} = 0$$
$$\text{igstPaise} = \left\lfloor \frac{\text{taxableAmountPaise} \times \text{gstRatePercent}}{100} \right\rfloor$$
$$\text{totalTaxPaise} = \text{igstPaise}$$

---

### 2.3 Section 52 TCS Withholding Formulation

Section 52 Tax Collection at Source (TCS) is computed on the net taxable base across the order:

#### Intra-State TCS (100 bps = 50 bps CGST + 50 bps SGST)
$$\text{tcsCgstPaise} = \left\lfloor \frac{\text{taxableSubtotalPaise} \times 50}{10000} \right\rfloor$$
$$\text{tcsSgstPaise} = \left\lfloor \frac{\text{taxableSubtotalPaise} \times 50}{10000} \right\rfloor$$
$$\text{tcsIgstPaise} = 0$$
$$\text{totalTcsPaise} = \text{tcsCgstPaise} + \text{tcsSgstPaise}$$

#### Inter-State TCS (100 bps IGST)
$$\text{tcsCgstPaise} = 0, \quad \text{tcsSgstPaise} = 0$$
$$\text{tcsIgstPaise} = \left\lfloor \frac{\text{taxableSubtotalPaise} \times 100}{10000} \right\rfloor$$
$$\text{totalTcsPaise} = \text{tcsIgstPaise}$$

---

### 2.4 Conserved Global Discount Allocation (Largest Remainder Method)

When a global promotional discount ($D_{\text{global}}$) is applied across $N$ line items with taxable values $v_1, v_2, \dots, v_N$ (where $V = \sum_{i=1}^N v_i$), the discount is apportioned using the **Hare-Niemeyer (Largest Remainder)** algorithm to prevent fractional penny loss:

1. **Compute Base Floor Allocations:**
   $$d_i = \left\lfloor \frac{D_{\text{global}} \times v_i}{V} \right\rfloor, \quad \text{remainder}_i = (D_{\text{global}} \times v_i) \pmod V$$
2. **Distribute Residual Paise:**
   The remaining unallocated paise $R = D_{\text{global}} - \sum_{i=1}^N d_i$ are assigned 1 paise at a time to the items with the largest fractional remainders $\text{remainder}_i$.
3. **Conservation Invariant:**
   $$\sum_{i=1}^N d_i \equiv D_{\text{global}}$$

---

### 2.5 Statutory HSN Tax Slabs

The engine supports all 5 official GST tax rate tiers:

| Slab | Rate (%) | Statutory Category | Representative HSN Codes |
|---|---|---|---|
| **Exempt** | 0% | Unprocessed agricultural products, essential food grains, raw milk | `0401` (Milk), `1001` (Wheat) |
| **Merit / Essential** | 5% | Life-saving pharmaceuticals, packaged edible oils, economy textiles | `3004` (Medicaments), `1507` (Soya Oil) |
| **Standard-1** | 12% | Processed foods, basic electronic components, diagnostic machinery | `8418` (Refrigerators), `9018` (Medical Instruments) |
| **Standard-2** | 18% | General electronics, commercial furniture, industrial capital goods | `8504` (Transformers), `9401` (Furniture) |
| **Demerit / Luxury**| 28% | Luxury motor vehicles, premium consumer electronics, aerated drinks | `8703` (Automobiles), `2202` (Beverages) |
| **Bullion** | 3% | Gold 24K/22K coins & bars, silver ingots, jewelry articles | `7113` (Jewelry), `7108` (Gold Bullion) |

---

## 3. Print-Ready HTML Invoice Generator

The HTML generation subsystem (`mandateEngine/tax/gstrInvoiceHtmlRenderer.py`) converts structured `GstrInvoicePayload` models into self-contained, responsive, print-ready HTML documents.

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                HTML INVOICE GENERATION PIPELINE                                  │
│                                                                                                  │
│  ┌──────────────────────┐      ┌──────────────────────────┐      ┌────────────────────────────┐  │
│  │     CartMandate      │ ───► │   generateGstrInvoice()  │ ───► │    GstrInvoicePayload      │  │
│  │ (Items, HSN, POS, DID│      │   - Arithmetic Enclave   │      │ (Immutable Pydantic Model) │  │
│  └──────────────────────┘      │   - RFC 8785 JCS Digest  │      └─────────────┬──────────────┘  │
│                                └──────────────────────────┘                    │                 │
│                                                                                ▼                 │
│                                ┌──────────────────────────┐      ┌────────────────────────────┐  │
│                                │ renderGstrInvoiceHtml()  │ ◄─── │  gstrInvoiceHtmlStyles.py  │  │
│                                │ - Sanitizes all inputs   │      │  - Base CSS & Print Media  │  │
│                                │ - Emits semantic DOM     │      │  - State Code Registry     │  │
│                                └────────────┬─────────────┘      └────────────────────────────┘  │
│                                             │                                                    │
│                                             ▼                                                    │
│                                ┌──────────────────────────┐                                      │
│                                │ Validated HTML5 Document │                                      │
│                                │ (Print & Screen Compliant│                                      │
│                                └──────────────────────────┘                                      │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Document Layout & Component Structure

The rendered HTML document contains five distinct sections structured to satisfy Rule 46:

1. **Header & Legal Classification Grid (`.header-grid`):**
   - Title: `TAX INVOICE`
   - Statutory Citation: `Issued under Section 31 of CGST Act, 2017 & Rule 46 of CGST Rules`
   - Invoice Metadata Badge: Invoice Number, Date, Supply Classification (`INTRA-STATE (CGST + SGST)` or `INTER-STATE (IGST)`).
2. **Entity Details Grid (`.details-grid`):**
   - **Seller / Supplier Box:** Legal Name, 15-character GSTIN, State Name & 2-Digit Code.
   - **Recipient / Place of Supply Box:** Recipient Legal Name, Place of Supply (POS) State & Code, Protocol Identifier (`RazorAgent Mesh v2.0`).
3. **Itemized Tax Breakdown Table (`.data-table`):**
   - Columns: `#`, `SKU Identifier`, `HSN`, `Qty`, `Unit Price`, `Taxable Amt`, `Rate`, `CGST`, `SGST`, `IGST`, `Line Total`.
   - Table Footer: Sum of taxable subtotal, total CGST, total SGST, total IGST, and total invoice value.
4. **Summary & TCS Grid (`.bottom-grid`):**
   - **Section 52 TCS Card:** Net Taxable Base, Statutory TCS Rate (100 bps), and Total TCS Withheld.
   - **Financial Summary Card:** Taxable Subtotal, Total GST, Shipping & Handling, Promotional Discount, and Grand Total.
5. **Cryptographic Audit Verification Stamp (`.audit-stamp`):**
   - Visual verified checkmark badge (`✓ Cryptographic Verification & Audit Stamp`).
   - 64-character hexadecimal SHA-256 digest rendered in a monospace code container.
   - Non-repudiation certification stamp with timestamp.

---

### 3.2 Responsive & Print-Optimized Stylesheet

The inline stylesheet (`gstrInvoiceHtmlStyles.py`) provides responsive desktop presentation and A4 portrait print styling:

```css
* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  color: #0f172a;
  background-color: #f8fafc;
  padding: 24px;
  line-height: 1.5;
}

.invoice-card {
  max-width: 880px;
  margin: 0 auto;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 32px;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 24px;
  font-size: 12px;
}

.data-table th {
  background-color: #0f172a;
  color: #ffffff;
  font-weight: 600;
  text-align: right;
  padding: 8px 10px;
}

.data-table th:first-child,
.data-table th:nth-child(2),
.data-table th:nth-child(3) {
  text-align: left;
}

.audit-hash-code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 11px;
  word-break: break-all;
  background: #dcfce7;
  padding: 4px 8px;
  border-radius: 4px;
  display: block;
  margin-top: 4px;
}

@media print {
  body {
    background: #ffffff !important;
    padding: 0 !important;
    font-size: 10pt !important;
    color: #000000 !important;
  }
  .invoice-card {
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
    max-width: 100% !important;
  }
  @page {
    size: A4 portrait;
    margin: 12mm 15mm;
  }
  tr, .section-box, .tcs-card, .summary-card, .audit-stamp {
    page-break-inside: avoid;
  }
  .data-table th {
    background-color: #0f172a !important;
    color: #ffffff !important;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }
  .tcs-card, .audit-stamp {
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }
}
```

---

### 3.3 Security & XSS Sanitization

To prevent Cross-Site Scripting (XSS) or HTML tag breakout from untrusted merchant or product metadata, all dynamic strings (SKU identifiers, product titles, invoice numbers, merchant legal names, GSTINs, and timestamps) are sanitized using `html.escape(value, quote=True)` prior to string template interpolation.

---

## 4. Cryptographic Audit Digest & Non-Repudiation

For complete e-invoicing audit compliance and tamper-evidence, every generated tax invoice computes a **Canonical JSON SHA-256 Digest** following **RFC 8785 (JSON Canonicalization Scheme - JCS)**.

### 4.1 Canonical JCS Payload Construction

The invoice dictionary is normalized with deterministic key ordering and zero unquoted whitespace:

```json
{
  "discountPaise": 2000,
  "grandTotalPaise": 475000,
  "invoiceDate": "2026-08-24T12:00:00+00:00",
  "invoiceNumber": "INV-2026-INTRA-001",
  "isIntraState": true,
  "lineItems": [
    {
      "cgstPaise": 36000,
      "gstRatePercent": 18,
      "hsnCode": "9401",
      "igstPaise": 0,
      "quantity": 2,
      "sgstPaise": 36000,
      "skuId": "SKU-CHAIR-001",
      "taxableAmountPaise": 400000,
      "totalLinePaise": 472000,
      "unitPricePaise": 200000
    }
  ],
  "merchantStateCode": "29",
  "placeOfSupplyStateCode": "29",
  "sellerGstin": "29AAAAA0000A1ZY",
  "shippingPaise": 5000,
  "taxableAmountPaise": 400000,
  "totalCgstPaise": 36000,
  "totalIgstPaise": 0,
  "totalSgstPaise": 36000,
  "totalTaxPaise": 72000,
  "totalTcsPaise": 4000
}
```

### 4.2 Cryptographic Hash Computation

The canonicalized UTF-8 bytes are passed through SHA-256:

$$\text{cryptographicAuditHash} = \text{SHA-256}\left(\text{JCS}(\text{InvoiceData})\right)$$

This yields a 64-character hexadecimal digest (e.g., `a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90`), which is stamped into the invoice document and recorded on the ledger for statutory tax reconciliation.

---

## 5. Indian GST 2-Digit State Code Registry

The tax engine includes an internal registry mapping all 37 official two-digit Indian GST state and Union Territory codes:

| Code | State / Union Territory | Code | State / Union Territory |
|---|---|---|---|
| `01` | Jammu & Kashmir | `20` | Jharkhand |
| `02` | Himachal Pradesh | `21` | Odisha |
| `03` | Punjab | `22` | Chhattisgarh |
| `04` | Chandigarh | `23` | Madhya Pradesh |
| `05` | Uttarakhand | `24` | Gujarat |
| `06` | Haryana | `26` | Dadra & Nagar Haveli and Daman & Diu |
| `07` | Delhi | `27` | Maharashtra |
| `08` | Rajasthan | `29` | Karnataka |
| `09` | Uttar Pradesh | `30` | Goa |
| `10` | Bihar | `31` | Lakshadweep |
| `11` | Sikkim | `32` | Kerala |
| `12` | Arunachal Pradesh | `33` | Tamil Nadu |
| `13` | Nagaland | `34` | Puducherry |
| `14` | Manipur | `35` | Andaman & Nicobar Islands |
| `15` | Mizoram | `36` | Telangana |
| `16` | Tripura | `37` | Andhra Pradesh |
| `17` | Meghalaya | `38` | Ladakh |
| `18` | Assam | `97` | Other Territory |
| `19` | West Bengal | | |

---

## 6. Verification & Automated Unit Testing

Verify the GSTR-1 tax calculation engine and HTML rendering pipeline using pytest:

```bash
# 1. Run GSTR-1 HTML invoice rendering unit tests
python -m pytest razoragentMesh/tests/unit/testGstrInvoiceEngineHtml.py -v

# 2. Run core GSTR tax engine calculations
python -m pytest razoragentMesh/tests/unit/testGstrInvoiceEngineCore.py -v

# 3. Run arithmetic enclave integer paise tests
python -m pytest razoragentMesh/tests/unit/testMandatePatcherTax.py -v
```
