"""Financial and tax arithmetic constants for the mandate engine."""

paisePerRupee: int = 100
basisPointsDivisor: int = 10000
percentDivisor: int = 100

tcsRateBasisPoints: int = 100
tcsCgstBasisPoints: int = 50
tcsSgstBasisPoints: int = 50
tcsIgstBasisPoints: int = 100

zeroPaise: int = 0
minValidGstRate: int = 0
maxValidGstRate: int = 28
validGstRates: frozenset[int] = frozenset({0, 5, 12, 18, 28})
