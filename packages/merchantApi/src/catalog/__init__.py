"""Catalog domain logic layer with dynamic pricing, HSN tax resolution, and vectorization."""

from .autoVectorizer import AutoVectorizer, synthesizeFacetDescription
from .catalogManager import CatalogManager
from .hsnTaxResolver import resolveHsnGstRate, validateHsnCode
from .priceNormalizer import ArithmeticDriftException, normalizeInrToPaise
from .pricingFormulaEngine import (
    SpotLinkedQuote,
    StalePriceQuoteException,
    computeSpotLinkedQuote,
    verifyQuoteNotExpired,
)
from .qdrantPayloadPatcher import QdrantPayloadPatcher
from .spotRateOracle import (
    SpotRateOracle,
    createInMemorySpotRateOracle,
    fallbackSpotRatesPerGramPaise,
)

__all__ = [
    "ArithmeticDriftException",
    "AutoVectorizer",
    "CatalogManager",
    "QdrantPayloadPatcher",
    "SpotLinkedQuote",
    "SpotRateOracle",
    "StalePriceQuoteException",
    "computeSpotLinkedQuote",
    "createInMemorySpotRateOracle",
    "fallbackSpotRatesPerGramPaise",
    "normalizeInrToPaise",
    "resolveHsnGstRate",
    "synthesizeFacetDescription",
    "validateHsnCode",
    "verifyQuoteNotExpired",
]
