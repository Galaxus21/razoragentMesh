// Publishes the compiled catalog fixtures to merchant-api on boot, so they are searchable.
//
// Only the 25 seeded industrial SKUs ever reached Qdrant. The 22 compiled office SKUs are
// quotable but invisible to search_catalog -- SKU-CHAIR-001 cannot be found by searching for an
// office chair -- because nothing had ever indexed them: their only consumers were catalogStore's
// own seed and lookup paths.
//
// This goes through the real POST /api/v1/merchant/{did}/catalog rather than extending the
// seeder, because the seeder does NOT embed: it requires a precomputed 384-dim vector in its JSON
// and writes a thinner payload with integer point ids, whereas the live route sanitizes, upserts
// to Redis, publishes the pub/sub event and indexes with real embeddings under uuid5 point ids.
// Going through the route makes the fixtures indistinguishable from merchant-published SKUs.
//
// Idempotent and non-fatal by contract: the route upserts, and no failure here may block or delay
// mcp-server starting. compose gates this container on the seeder completing, NOT on merchant-api
// being healthy, so a cold start racing merchant-api is expected and must simply be reported.

import { initialCatalogFixtures } from "./catalogFixtures.js";
import { resolveMerchantApiUrl } from "../constants/catalogSearchConstants.js";
import { CatalogSkuItem } from "../types/mcpToolTypes.js";

/** The merchant these fixtures are published as. They carry no merchantDid of their own. */
export const fixtureMerchantDid = "did:mesh:merchant_razoragent_demo_01";
const fixtureOriginPincode = "560001";
const publishTimeoutMs = 5000;

export interface FixturePublishSummary {
  readonly published: number;
  readonly failed: number;
  readonly skipped: boolean;
}

/**
 * Maps a compiled fixture onto UniversalProductListing.
 *
 * The parent model is extra="forbid", so `brand`, `weightGrams` and `dimensionsCm` must be
 * dropped rather than passed through -- sending them is a 422, not a warning. `name` is `title`
 * on the wire, and merchantDid is synthesized because a fixture has no merchant of its own.
 */
export function toUniversalListing(sku: CatalogSkuItem): Record<string, unknown> {
  return {
    skuId: sku.skuId,
    merchantDid: fixtureMerchantDid,
    title: sku.name,
    description: sku.description,
    category: sku.category,
    hsnCode: sku.hsnCode,
    gstRatePercent: sku.gstRatePercent,
    baseUnitPricePaise: sku.baseUnitPricePaise,
    availableStock: sku.availableStock,
    originPincode: sku.originPincode ?? fixtureOriginPincode,
    volumeTiers: sku.volumeTiers.map((tier) => ({
      minQuantity: tier.minQuantity,
      discountBps: tier.discountBps
    })),
    ...(sku.promotions && sku.promotions.length > 0 ? { promotions: sku.promotions } : {})
  };
}

async function publishOne(baseUrl: string, sku: CatalogSkuItem): Promise<boolean> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), publishTimeoutMs);
  try {
    const response = await fetch(
      `${baseUrl}/api/v1/merchant/${encodeURIComponent(fixtureMerchantDid)}/catalog`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(toUniversalListing(sku)),
        signal: controller.signal
      }
    );
    if (!response.ok) {
      process.stderr.write(
        `[MCP] Could not index fixture ${sku.skuId}: HTTP ${response.status}. ` +
          "It stays quotable but will not appear in search_catalog.\n"
      );
      return false;
    }
    return true;
  } catch (error: unknown) {
    process.stderr.write(
      `[MCP] Could not index fixture ${sku.skuId}: ${String(error)}. ` +
        "It stays quotable but will not appear in search_catalog.\n"
    );
    return false;
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Publishes every compiled fixture. Never throws: a caller may await it or not, and mcp-server
 * must start either way.
 */
export async function indexCompiledFixtures(
  fixtures: readonly CatalogSkuItem[] = initialCatalogFixtures
): Promise<FixturePublishSummary> {
  const baseUrl = resolveMerchantApiUrl().replace(/\/+$/, "");
  let published = 0;
  let failed = 0;

  for (const sku of fixtures) {
    // Sequential on purpose: this runs at boot beside everything else starting up, and firing 22
    // concurrent embeddings at a merchant-api that may still be warming is how a cold start turns
    // into a thundering herd.
    if (await publishOne(baseUrl, sku)) {
      published += 1;
    } else {
      failed += 1;
    }
  }

  if (failed > 0) {
    process.stderr.write(
      `[MCP] Indexed ${published}/${fixtures.length} compiled SKUs into merchant-api. ` +
        `${failed} could not be indexed and will be quotable but not searchable.\n`
    );
  }
  return { published, failed, skipped: false };
}
