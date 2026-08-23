"""Commercial contract AST Pydantic schema."""

from pydantic import BaseModel, ConfigDict, Field


class CommercialContractAst(BaseModel):
    """Immutable Commercial Contract AST representing agreed negotiation terms."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    skuId: str = Field(min_length=1)
    quantity: int = Field(gt=0)
    agreedUnitPricePaise: int = Field(gt=0)
    taxableSubtotalPaise: int = Field(gt=0)
    totalTaxPaise: int = Field(ge=0)
    totalGrossPaise: int = Field(gt=0)
    settlementTurns: int = Field(ge=1)
    buyerAgentDid: str = Field(min_length=1)
    merchantDid: str = Field(min_length=1)
    contractTimestamp: int = Field(gt=0)


__all__ = ["CommercialContractAst"]
