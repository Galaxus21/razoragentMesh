"""GSTR-1 invoice HTML styling and state code registry."""

gstStateCodeToName: dict[str, str] = {
    "01": "Jammu & Kashmir",
    "02": "Himachal Pradesh",
    "03": "Punjab",
    "04": "Chandigarh",
    "05": "Uttarakhand",
    "06": "Haryana",
    "07": "Delhi",
    "08": "Rajasthan",
    "09": "Uttar Pradesh",
    "10": "Bihar",
    "11": "Sikkim",
    "12": "Arunachal Pradesh",
    "13": "Nagaland",
    "14": "Manipur",
    "15": "Mizoram",
    "16": "Tripura",
    "17": "Meghalaya",
    "18": "Assam",
    "19": "West Bengal",
    "20": "Jharkhand",
    "21": "Odisha",
    "22": "Chhattisgarh",
    "23": "Madhya Pradesh",
    "24": "Gujarat",
    "26": "Dadra & Nagar Haveli and Daman & Diu",
    "27": "Maharashtra",
    "29": "Karnataka",
    "30": "Goa",
    "31": "Lakshadweep",
    "32": "Kerala",
    "33": "Tamil Nadu",
    "34": "Puducherry",
    "35": "Andaman & Nicobar Islands",
    "36": "Telangana",
    "37": "Andhra Pradesh",
    "38": "Ladakh",
    "97": "Other Territory",
}


def resolveStateName(stateCode: str) -> str:
    """Resolves 2-digit GST state code to official Indian state or UT name."""
    cleanCode = stateCode.strip()
    return gstStateCodeToName.get(cleanCode, f"State Code {cleanCode}")


invoiceBaseStyles: str = """
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
  .header-grid {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    border-bottom: 2px solid #0f172a;
    padding-bottom: 20px;
    margin-bottom: 24px;
  }
  .title-area h1 {
    font-size: 24px;
    font-weight: 800;
    color: #0f172a;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .title-area p {
    font-size: 12px;
    color: #64748b;
    margin-top: 4px;
  }
  .meta-badge {
    text-align: right;
    font-size: 13px;
  }
  .meta-badge .invoice-num {
    font-size: 16px;
    font-weight: 700;
    color: #0f172a;
  }
  .details-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
    margin-bottom: 24px;
    font-size: 13px;
  }
  .section-box {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 14px;
  }
  .section-box h3 {
    font-size: 12px;
    text-transform: uppercase;
    color: #475569;
    margin-bottom: 8px;
    letter-spacing: 0.5px;
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
  .data-table th:first-child, .data-table th:nth-child(2), .data-table th:nth-child(3) {
    text-align: left;
  }
  .data-table td {
    padding: 8px 10px;
    border-bottom: 1px solid #e2e8f0;
    text-align: right;
  }
  .data-table td:first-child, .data-table td:nth-child(2), .data-table td:nth-child(3) {
    text-align: left;
  }
  .data-table tfoot td {
    font-weight: 700;
    background: #f1f5f9;
    border-top: 2px solid #cbd5e1;
  }
  .bottom-grid {
    display: grid;
    grid-template-columns: 1.2fr 1fr;
    gap: 20px;
    margin-bottom: 24px;
  }
  .tcs-card {
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    border-radius: 6px;
    padding: 14px;
    font-size: 12px;
  }
  .tcs-card h3 {
    color: #1e40af;
    font-size: 12px;
    text-transform: uppercase;
    margin-bottom: 8px;
  }
  .summary-card {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 14px;
    font-size: 13px;
  }
  .summary-row {
    display: flex;
    justify-content: space-between;
    padding: 4px 0;
  }
  .grand-total-row {
    display: flex;
    justify-content: space-between;
    padding: 8px 0;
    border-top: 2px solid #0f172a;
    margin-top: 8px;
    font-size: 15px;
    font-weight: 800;
    color: #0f172a;
  }
  .audit-stamp {
    background: #f0fdf4;
    border: 1px solid #bbf7d0;
    border-radius: 6px;
    padding: 14px;
    font-size: 11px;
    color: #166534;
  }
  .audit-stamp h4 {
    font-size: 12px;
    text-transform: uppercase;
    margin-bottom: 4px;
    display: flex;
    align-items: center;
    gap: 6px;
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
"""
