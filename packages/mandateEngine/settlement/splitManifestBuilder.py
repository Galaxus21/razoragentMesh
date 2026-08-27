"""Split manifest builder for 3-way route payouts (merchant, protocol, logistics)."""

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from ..mandates.cartMandateSchema import CartMandate
from .settlementExceptions import ArithmeticDriftException

defaultProtocolFeeAccount: str = "acc_protocol_fee"
defaultProtocolFeePaise: int = 50
defaultLogisticsAccount: str = "acc_logistics_delhivery"


class SplitTransferManifest(BaseModel):
    """Calculated split manifest for merchant, protocol, and logistics accounts."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    merchantAccount: str = Field(min_length=1)
    merchantAmountPaise: int = Field(gt=0)
    protocolFeeAccount: str = Field(min_length=1)
    protocolFeePaise: int = Field(ge=0)
    logisticsAccount: str = Field(min_length=1)
    logisticsAmountPaise: int = Field(ge=0)
    totalPaise: int = Field(gt=0)


def buildSplitManifest(
    cartMandate: CartMandate,
    merchantAccount: str,
    protocolFeeAccount: str = defaultProtocolFeeAccount,
    protocolFeePaise: int = defaultProtocolFeePaise,
    logisticsAccount: str = defaultLogisticsAccount,
    customProtocolFeePaise: Optional[int] = None,
) -> SplitTransferManifest:
    """Computes split amounts for merchant, logistics partner, and protocol fee."""
    protoFee = customProtocolFeePaise if customProtocolFeePaise is not None else protocolFeePaise
    shipping = cartMandate.shippingPaise
    grossTotal = cartMandate.totalPaise

    totalDeductions = protoFee + shipping
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
        totalPaise=grossTotal,
    )

