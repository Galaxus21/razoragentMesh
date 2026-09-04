// A sale an agent is shown on a product it does NOT buy.
//
// Measured across 7 unasked runs, no agent ever volunteered an upcoming sale; the receipt notice
// added by execute_settlement only reaches the buyer of the promoted SKU. The case that actually
// happens is the agent searching, seeing SKU A on sale, buying SKU B, and never mentioning A --
// so the sale has to travel with every search result, including the ones it rejects.
// (AUDIT_ARCHIVE item 48.)

import { describe, it, before, after } from "node:test";
import assert from "node:assert/strict";
import { searchCatalog } from "../src/tools/catalogSearcher.js";
import { browseCatalog } from "../src/tools/catalogBrowser.js";
import { CatalogStore } from "../src/catalog/catalogStore.js";
import { mcpToolsManifest } from "../src/constants/toolsManifest.js";
import { toolSearchCatalog, millisPerSecond } from "../src/constants/protocolConstants.js";
import type { CatalogSkuItem, ScheduledPromotion } from "../src/types/mcpToolTypes.js";

const nowUnix = Math.floor(Date.now() / millisPerSecond);
const oneHour = 3600;

function listing(skuId: string, promotions: readonly ScheduledPromotion[]): CatalogSkuItem {
  return {
    skuId,
    name: `Bench listing ${skuId}`,
    category: "Test Bench",
    description: "A listing published for the search sale-notice tests.",
    hsnCode: "94013000",
    gstRatePercent: 18,
    baseUnitPricePaise: 100000,
    availableStock: 10,
    volumeTiers: [],
    promotions
  };
}

function promotion(campaignId: string, startsAtUnix: number, endsAtUnix: number): ScheduledPromotion {
  return { campaignId, name: `Sale ${campaignId}`, startsAtUnix, endsAtUnix, discountBps: 2000 };
}

const benchStore = new CatalogStore([
  listing("SKU-BENCH-SALE", [promotion("CAMP-SOON", nowUnix + oneHour, nowUnix + 2 * oneHour)]),
  listing("SKU-BENCH-PLAIN", []),
  listing("SKU-BENCH-BADWINDOW", [promotion("CAMP-BROKEN", nowUnix + 2 * oneHour, nowUnix + oneHour)])
]);

/** The ranked hits merchantApi returns, in its own camelCase wire shape. */
const upstreamHits = [
  { skuId: "SKU-BENCH-PLAIN", title: "Bench listing SKU-BENCH-PLAIN", score: 0.71 },
  { skuId: "SKU-BENCH-SALE", title: "Bench listing SKU-BENCH-SALE", score: 0.42 },
  { skuId: "SKU-NOT-IN-STORE", title: "Indexed elsewhere", score: 0.31 },
  { skuId: "SKU-BENCH-BADWINDOW", title: "Bench listing SKU-BENCH-BADWINDOW", score: 0.12 }
];

const realFetch = globalThis.fetch;

function stubSearchUpstream(): void {
  globalThis.fetch = (async () =>
    new Response(
      JSON.stringify({
        results: upstreamHits,
        resultCount: upstreamHits.length,
        embeddingMode: "model",
        rankingQuality: "Ranked by semantic similarity using the all-MiniLM-L6-v2 model.",
        indexAvailable: true
      }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    )) as typeof globalThis.fetch;
}

async function searchBench(): Promise<ReadonlyArray<Record<string, unknown>>> {
  const result = await searchCatalog({ query_text: "a bench listing" }, benchStore, nowUnix);
  return result.results as ReadonlyArray<Record<string, unknown>>;
}

function hitFor(hits: ReadonlyArray<Record<string, unknown>>, skuId: string): Record<string, unknown> {
  const hit = hits.find((candidate) => candidate.skuId === skuId);
  assert.ok(hit, `${skuId} must be in the results`);
  return hit;
}

describe("search_catalog carries a scheduled sale on results the agent did not buy", () => {
  before(stubSearchUpstream);
  after(() => {
    globalThis.fetch = realFetch;
  });

  it("attaches next_promotion to a ranked hit whose merchant has a sale scheduled", async () => {
    const promoted = hitFor(await searchBench(), "SKU-BENCH-SALE");
    const next = promoted.next_promotion as Record<string, unknown> | undefined;
    assert.ok(next, "a SKU with a scheduled sale must say so in the search result");
    assert.equal(next.campaign_id, "CAMP-SOON");
    assert.equal(next.starts_at_unix, nowUnix + oneHour);
    assert.ok((next.expected_savings_paise as number) > 0);
  });

  it("attaches it to a hit ranked BELOW the one an agent would take", async () => {
    // The whole finding: the agent buys the top hit and is never told the cheaper-tomorrow SKU
    // it scrolled past. SKU-BENCH-SALE ranks second here on purpose.
    const hits = await searchBench();
    assert.equal(hits[0].skuId, "SKU-BENCH-PLAIN", "the plain SKU must outrank the promoted one");
    assert.ok(hitFor(hits, "SKU-BENCH-SALE").next_promotion, "a rejected result still carries its sale");
  });

  it("reports the same sale browse_catalog reports, with the same numbers", async () => {
    // Two discovery surfaces must not become two opinions about one merchant's campaign.
    const searched = hitFor(await searchBench(), "SKU-BENCH-SALE").next_promotion;
    const browsed = browseCatalog({ limit: 100 }, benchStore, nowUnix).items.find(
      (item) => item.sku_id === "SKU-BENCH-SALE"
    )?.next_promotion;
    assert.deepEqual(searched, browsed);
  });

  it("leaves a hit with no scheduled sale exactly as the ranker returned it", async () => {
    const plain = hitFor(await searchBench(), "SKU-BENCH-PLAIN");
    assert.equal("next_promotion" in plain, false);
    assert.equal(plain.score, 0.71);
  });

  it("passes through a hit this process's catalog does not hold, rather than dropping it", async () => {
    // Search ranks a wider index than the in-process store carries. Hiding a result because no
    // local sale could be resolved would be worse than saying nothing about its sales.
    const foreign = hitFor(await searchBench(), "SKU-NOT-IN-STORE");
    assert.equal("next_promotion" in foreign, false);
    assert.equal(foreign.title, "Indexed elsewhere");
  });

  it("keeps listing a SKU whose promotion cannot be priced", async () => {
    // An inverted window throws in the evaluator. On a discovery surface that must cost the
    // sale notice, never the result.
    const broken = hitFor(await searchBench(), "SKU-BENCH-BADWINDOW");
    assert.equal("next_promotion" in broken, false);
  });

  it("tells the agent, in the manifest, that it must relay a sale it was shown", async () => {
    // The guard and the description ship together: a field an agent is never told to read is a
    // field that changes no behaviour.
    const entry = mcpToolsManifest.find((tool) => tool.name === toolSearchCatalog);
    assert.ok(entry, "search_catalog must be in the manifest");
    assert.match(entry.description, /next_promotion/);
    assert.match(entry.description, /MUST say so in your final answer/);
    assert.match(entry.description, /did not buy/);
  });
});
