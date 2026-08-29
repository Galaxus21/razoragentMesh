"""Financial and tax arithmetic constants for the mandate engine."""

# Application & Service Metadata
defaultEngineTitle: str = "RazorAgent Mandate Engine"
defaultEngineVersion: str = "2.0.0"

# Financial Unit Divisors & Percentages
paisePerRupee: int = 100
basisPointsDivisor: int = 10000
percentDivisor: int = 100
# Divisor for the intra-state half-rate split (basisPointsDivisor * 2).
# Applying it once (rather than halving the rate, then dividing again) keeps
# CGST and SGST exactly equal and the total exactly conserved.
intraStateHalfBpsDivisor: int = 20000
millisecondsPerSecond: int = 1000

# TCS Statutory Rates (Section 52, CGST Act 2017 -- Tax Collected at Source by an
# electronic commerce operator on the net value of taxable supplies).
#
# Source:        Notification No. 15/2024-Central Tax, dated 10 July 2024, which amends
#                Notification No. 52/2018-Central Tax (20 September 2018) by substituting
#                "half per cent" with "0.25 per cent". The parallel reduction for
#                inter-State supplies is Notification No. 02/2024-Integrated Tax.
#                Recommended by the 53rd GST Council meeting.
# Effect:        Combined TCS fell from 1.00% to 0.50% with effect from 10 July 2024.
#                Intra-State: 0.25% CGST + 0.25% SGST. Inter-State: 0.50% IGST.
# Last verified: 2026-08-29, against the notification reference above. The CBIC PDF portal
#                (taxinformation.cbic.gov.in) could not be fetched directly at that time, so
#                re-confirm against the primary PDF before relying on this in production.
# Re-verify:     Whenever a GST Council meeting changes Section 52 rates. See
#                docs/STATUTORY_RATES.md for the review procedure.
tcsRateBasisPoints: int = 50
tcsCgstBasisPoints: int = 25
tcsSgstBasisPoints: int = 25
tcsIgstBasisPoints: int = 50

# Financial Limits & GST Rates
zeroPaise: int = 0
minValidGstRate: int = 0
maxValidGstRate: int = 28
validGstRates: frozenset[int] = frozenset({0, 5, 12, 18, 28})

# Identifiers & Prefixes
transferIdPrefix: str = "trf_"

# Settlement Transfer Purpose Notes
purposeMerchantPayout: str = "merchant_payout"
purposeMerchantNetSettlement: str = "merchant_net_settlement"
purposeProtocolFee: str = "protocol_fee"
purposeLogistics: str = "logistics_fee"
purposeLogisticsSlaSettlement: str = "logistics_sla_settlement"
purposeTcsWithholding: str = "tcs_section_52_withholding"

__all__ = [
    "basisPointsDivisor",
    "defaultEngineTitle",
    "defaultEngineVersion",
    "intraStateHalfBpsDivisor",
    "maxValidGstRate",
    "millisecondsPerSecond",
    "minValidGstRate",
    "paisePerRupee",
    "percentDivisor",
    "purposeLogistics",
    "purposeLogisticsSlaSettlement",
    "purposeMerchantNetSettlement",
    "purposeMerchantPayout",
    "purposeProtocolFee",
    "purposeTcsWithholding",
    "tcsCgstBasisPoints",
    "tcsIgstBasisPoints",
    "tcsRateBasisPoints",
    "tcsSgstBasisPoints",
    "transferIdPrefix",
    "validGstRates",
    "zeroPaise",
]
