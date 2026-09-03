"""Applies the Layer 0 ingress shield to merchant-supplied catalog text.

`packages/catalogSanitizer` was written, tested, exported, named in the README architecture
diagram, in GUIDE.md, and listed as a live component in the dashboard's `protocolLayerMap.ts` --
and called by nothing on any ingress path. Every merchant listing reached the catalog with at
most a `.strip()` on it, and the Shopify path did not even do that: it passed raw `body_html`
straight through.

This module is the missing call. It exists rather than the routes each calling
`cleanAndTruncateText` themselves so that the three ingestion paths cannot drift apart -- one
rule, one implementation (V-03).

Why the low-level helper and not `sanitizeMerchantSkuQuote`: that function returns a
`SanitizedSkuQuote`, a different model from the `UniversalProductListing` the ingestion paths
carry (no merchantDid, no category, no facets; it adds quoteHash and taxBreakdown). It cannot be
dropped in. `cleanAndTruncateText` is shape-agnostic and applies as-is.

What this does NOT do: validate prices, stock or tax. Those are `sanitizeMerchantSkuQuote`'s job
on the quote path, and duplicating them here would be a second implementation of rules that
already have one.
"""

from typing import TypeVar

from razoragentMesh.packages.catalogSanitizer import (
    cleanAndTruncateText,
    maxDescriptionLength,
    maxTitleLength,
)

# Bound to the schema's own field, not the sanitizer's default, so a listing that survives this
# pass cannot then be rejected by Pydantic for length.
ListingT = TypeVar("ListingT")


def sanitizeListingText(listing: ListingT) -> ListingT:
    """Returns a copy of the listing with its free-text fields scrubbed and NFC-normalized.

    Title and description are the two fields a merchant fully controls and the two that reach an
    embedding model and an agent's context, which is what makes them the injection surface. A
    zero-width payload or a Unicode Tags sequence in a title is invisible to a human reviewing
    the catalog and legible to a model reading it.

    Returns the listing unchanged if both fields are already clean, so an untouched listing keeps
    object identity and this stays cheap on the bulk path.
    """
    cleanedTitle = cleanAndTruncateText(listing.title, maxTitleLength)
    cleanedDescription = cleanAndTruncateText(listing.description, maxDescriptionLength)

    if cleanedTitle == listing.title and cleanedDescription == listing.description:
        return listing

    # A title that was ENTIRELY hidden characters would clean to "" and fail the schema's
    # min_length. Keeping the original in that case surfaces it as a validation error naming the
    # field, rather than as an opaque empty-string write.
    if not cleanedTitle:
        cleanedTitle = listing.title

    return listing.model_copy(
        update={"title": cleanedTitle, "description": cleanedDescription}
    )


__all__ = ["sanitizeListingText"]
