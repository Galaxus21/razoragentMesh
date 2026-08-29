"""Split manifest builder for 3-way route payouts (merchant, protocol, logistics)."""

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from ..mandates.cartMandateSchema import CartMandate
from ..verification.arithmeticEnclave import computeTcsWithholding
from .settlementExceptions import ArithmeticDriftException

defaultProtocolFeeAccount: str = "acc_protocol_fee"
defaultProtocolFeePaise: int = 50
defaultLogisticsAccount: str = "acc_logistics_delhivery"
defaultTcsHoldingAccount: str = "acc_tcs_withholding"


class SplitTransferManifest(BaseModel):
    """Calculated split manifest for merchant, protocol, and logistics accounts."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    merchantAccount: str = Field(min_length=1)
    merchantAmountPaise: int = Field(gt=0)
    protocolFeeAccount: str = Field(min_length=1)
    protocolFeePaise: int = Field(ge=0)
    logisticsAccount: str = Field(min_length=1)
    logisticsAmountPaise: int = Field(ge=0)
    tcsHoldingAccount: str = Field(min_length=1, default=defaultTcsHoldingAccount)
    tcsWithheldPaise: int = Field(ge=0, default=0)
    totalPaise: int = Field(gt=0)


def buildSplitManifest(
    cartMandate: CartMandate,
    merchantAccount: str,
    protocolFeeAccount: str = defaultProtocolFeeAccount,
    protocolFeePaise: int = defaultProtocolFeePaise,
    logisticsAccount: str = defaultLogisticsAccount,
    customProtocolFeePaise: Optional[int] = None,
    tcsHoldingAccount: str = defaultTcsHoldingAccount,
) -> SplitTransferManifest:
    """Computes split amounts for merchant, logistics partner, protocol fee, and TCS.

    Section 52 makes the electronic commerce operator responsible for *collecting* TCS from
    the supplier and remitting it to the exchequer, so it must be withheld from the merchant's
    payout rather than merely reported on the invoice. It is routed to a dedicated holding
    account so the amount owed to the exchequer is never commingled with protocol revenue.
    """
    protoFee = customProtocolFeePaise if customProtocolFeePaise is not None else protocolFeePaise
    shipping = cartMandate.shippingPaise
    grossTotal = cartMandate.totalPaise

    isIntraState = cartMandate.merchantStateCode == cartMandate.buyerDeliveryStateCode
    tcsWithheld = computeTcsWithholding(cartMandate.taxableSubtotalPaise, isIntraState)["totalTcsPaise"]

    totalDeductions = protoFee + shipping + tcsWithheld
    if totalDeductions >= grossTotal:
        raise ArithmeticDriftException(
            f"Settlement overdraft: total deductions ({totalDeductions} paise) "
            f"exceed or equal gross settlement ({grossTotal} paise)"
        )

    merchantNet = grossTotal - totalDeductions

    return SplitTransferManifest(
        merchantAccount=merchantAccount,
        merchantAmountPaise=merchantNet,
        protocolFeeAccount=protocolFeeAccount,
        protocolFeePaise=protoFee,
        logisticsAccount=logisticsAccount,
        logisticsAmountPaise=shipping,
        tcsHoldingAccount=tcsHoldingAccount,
        tcsWithheldPaise=tcsWithheld,
        totalPaise=grossTotal,
    )

