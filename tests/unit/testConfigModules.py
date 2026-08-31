"""Unit tests for centralized config modules (mandateEngine, x402Gateway, merchantApi) and allergen parsing."""

import os
import pytest
from pydantic import ValidationError

from razoragentMesh.packages.mandateEngine.config import (
    MandateEngineSettings,
    defaultMandateSettings,
    getMandateEngineSettings,
)
from razoragentMesh.packages.x402Gateway.src.config import (
    X402GatewaySettings,
    defaultGatewaySettings,
    getGatewaySettings,
)
from razoragentMesh.packages.merchantApi.src.config import (
    MerchantApiSettings,
    defaultMerchantSettings,
    getMerchantApiSettings,
)
from razoragentMesh.packages.merchantApi.src.adapters.shopifyStoreAdapter import (
    _extractShopifyAllergens,
    _parseAllergenPrefixSection,
    excludedAllergenWords,
)


def testMandateEngineSettingsDefaults() -> None:
    """Verifies default values and types for MandateEngineSettings."""
    settings = getMandateEngineSettings()
    assert isinstance(settings.redisUrl, str)
    assert settings.redisUrl.startswith("redis://")
    assert defaultMandateSettings is not None


def testMandateEngineSettingsImmutability() -> None:
    """Verifies MandateEngineSettings is frozen and rejects mutations and extra fields."""
    settings = MandateEngineSettings(redisUrl="redis://test:6379/1")
    with pytest.raises(ValidationError):
        settings.redisUrl = "redis://other:6379/2"  # type: ignore

    with pytest.raises(ValidationError):
        MandateEngineSettings(unknownField="invalid")  # type: ignore


def testX402GatewaySettingsDefaults() -> None:
    """Verifies default values and immutability for X402GatewaySettings."""
    settings = getGatewaySettings()
    assert isinstance(settings.redisUrl, str)
    assert defaultGatewaySettings is not None

    with pytest.raises(ValidationError):
        settings.redisUrl = "redis://other:6379/2"  # type: ignore


def testMerchantApiSettingsDefaults() -> None:
    """Verifies default values and immutability for MerchantApiSettings."""
    settings = getMerchantApiSettings()
    assert isinstance(settings.redisUrl, str)
    assert defaultMerchantSettings is not None

    with pytest.raises(ValidationError):
        settings.redisUrl = "redis://other:6379/2"  # type: ignore


def testShopifyAllergenPrefixParser() -> None:
    """Verifies helper function _parseAllergenPrefixSection parses tokens properly."""
    rawTags = "organic, gluten-free, allergens:peanuts, soy, milk; wheat"
    lowerTags = rawTags.lower()
    extracted = _parseAllergenPrefixSection(rawTags, lowerTags, "allergens:")
    assert "peanuts" in extracted
    assert "soy" in extracted
    assert "milk" in extracted
    assert "wheat" in extracted


def testShopifyAllergenExcludedWords() -> None:
    """Verifies excluded words are filtered out by allergen extractor."""
    assert "organic" in excludedAllergenWords
    assert "vegan" in excludedAllergenWords
    rawTags = "allergens:peanuts, organic, vegan, tree nuts:almonds"
    allergens = _extractShopifyAllergens(rawTags)
    assert "peanuts" in allergens
    assert "organic" not in allergens
    assert "vegan" not in allergens


def testShopifyAllergenEmptyAndNone() -> None:
    """Verifies empty, whitespace, and None tags return empty list."""
    assert _extractShopifyAllergens(None) == []
    assert _extractShopifyAllergens("") == []
    assert _extractShopifyAllergens("   ") == []
    assert _extractShopifyAllergens("tag1, tag2, tag3") == []
