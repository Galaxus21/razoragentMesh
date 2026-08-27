"""Cart difference and price delta computation for mandate patching."""

from razoragentMesh.packages.mandateEngine import CartMandate


def generateCartDiff(
    originalCartMandate: CartMandate,
    failedSkuId: str,
    substituteUnitPricePaise: int,
) -> int:
    """Computes the price delta in paise between the substitute SKU and the original SKU."""
    origItem = next((item for item in originalCartMandate.items if item.skuId == failedSkuId), None)
    origPrice = origItem.unitPricePaise if origItem else 0
    return substituteUnitPricePaise - origPrice


__all__ = ["generateCartDiff"]
