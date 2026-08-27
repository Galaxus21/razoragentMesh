"""Financial and tax arithmetic constants for the mandate engine."""

# Application & Service Metadata
defaultEngineTitle: str = "RazorAgent Mandate Engine"
defaultEngineVersion: str = "2.0.0"

# Financial Unit Divisors & Percentages
paisePerRupee: int = 100
basisPointsDivisor: int = 10000
percentDivisor: int = 100
millisecondsPerSecond: int = 1000

# TCS Statutory Rates
tcsRateBasisPoints: int = 100
tcsCgstBasisPoints: int = 50
tcsSgstBasisPoints: int = 50
tcsIgstBasisPoints: int = 100

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

__all__ = [
    "basisPointsDivisor",
    "defaultEngineTitle",
    "defaultEngineVersion",
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
    "tcsCgstBasisPoints",
    "tcsIgstBasisPoints",
    "tcsRateBasisPoints",
    "tcsSgstBasisPoints",
    "transferIdPrefix",
    "validGstRates",
    "zeroPaise",
]
