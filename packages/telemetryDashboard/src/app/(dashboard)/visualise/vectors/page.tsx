"use client";

// Layer 1's index, made visible.
//
// Every other screen shows what the mesh decided. This one shows what it decided *from*: the
// actual Qdrant collection a buyer agent's search_catalog call ranks against. The point of the
// panel is falsifiability -- a judge can type a query, watch a specific SKU win, and read the
// cosine that made it win, rather than taking "semantic discovery" on trust.

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { usePersistentState } from "@/hooks/usePersistentState";
import Link from "next/link";
import { ChevronRight, Database, Loader2, Search, ShieldAlert, Wand2 } from "lucide-react";
import { panelClass } from "@/constants/playgroundConstants";
import { formatPaiseToInr } from "@/lib/currencyFormatter";
import { embeddingModeModel } from "@/constants/vectorIndexConstants";
import VectorIndexMap, {
  categoryLegend,
  type HealAnnotation,
  type HitAnnotation
} from "@/components/vectorIndexMap";
import type {
  CatalogSearchResponse,
  OosHealingResponse,
  VectorIndexResponse
} from "@/types/vectorIndexTypes";

const pageTitle = "Vector Index";
const pageDescription =
  "The Qdrant collection Layer 1 searches. Every point is a real catalog embedding; every score below is the cosine that a buyer agent's search_catalog call would receive.";

// The query the pitch uses on camera. Chosen because its result set separates cleanly: both
// acoustic pods score above 0.66 and the first non-pod falls to 0.27, so the cliff between an
// answer and noise is legible on screen without anyone reading the numbers aloud.
const exampleQuery = "soundproof phone booth for an open plan office";

function StatCell({
  label,
  value,
  hint
}: {
  readonly label: string;
  readonly value: string;
  readonly hint?: string;
}): React.JSX.Element {
  return (
    <div className="rounded-md border border-borderSubtle bg-surfaceContainer px-3 py-2">
      <div className="text-[10px] uppercase tracking-wide text-textMuted">{label}</div>
      <div className="mt-0.5 font-mono text-sm font-semibold text-textPrimary">{value}</div>
      {hint ? <div className="mt-0.5 text-[10px] text-textMuted">{hint}</div> : null}
    </div>
  );
}

export default function VectorIndexPage(): React.JSX.Element {
  const [index, setIndex] = useState<VectorIndexResponse | null>(null);
  const [indexError, setIndexError] = useState<string | null>(null);

  // The ranked scores are the evidence this panel exists to show, so they outlive a trip to
  // another tab. The index itself is refetched on mount and is deliberately not stored.
  const [queryText, setQueryText] = usePersistentState<string>(
    "razoragent.vectorIndex.queryText.v1",
    exampleQuery
  );
  const [search, setSearch] = usePersistentState<CatalogSearchResponse | null>(
    "razoragent.vectorIndex.search.v1",
    null
  );
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  const [heal, setHeal] = usePersistentState<OosHealingResponse | null>(
    "razoragent.vectorIndex.heal.v1",
    null
  );
  const [healing, setHealing] = useState(false);
  const [selectedSkuId, setSelectedSkuId] = usePersistentState<string | null>(
    "razoragent.vectorIndex.selectedSku.v1",
    null
  );

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const response = await fetch("/api/mesh/vectors", { cache: "no-store" });
        const body = (await response.json()) as VectorIndexResponse;
        if (!cancelled) {
          setIndex(body);
        }
      } catch (error: unknown) {
        if (!cancelled) {
          setIndexError(error instanceof Error ? error.message : String(error));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const runSearch = useCallback(async () => {
    const trimmed = queryText.trim();
    if (trimmed.length === 0) {
      return;
    }
    setSearching(true);
    setSearchError(null);
    setHeal(null);
    try {
      const response = await fetch("/api/mesh/vectors/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: "search", queryText: trimmed, limit: 5 })
      });
      const body = (await response.json()) as CatalogSearchResponse & { detail?: string };
      if (!response.ok) {
        setSearchError(body.detail ?? `Search failed with HTTP ${response.status}.`);
        setSearch(null);
        return;
      }
      setSearch(body);
    } catch (error: unknown) {
      setSearchError(error instanceof Error ? error.message : String(error));
      setSearch(null);
    } finally {
      setSearching(false);
    }
  }, [queryText]);

  const runHeal = useCallback(async (failedSkuId: string) => {
    setHealing(true);
    setSearch(null);
    setSearchError(null);
    try {
      const response = await fetch("/api/mesh/vectors/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: "heal", failedSkuId, requestedQuantity: 1 })
      });
      const body = (await response.json()) as OosHealingResponse;
      setHeal(response.ok ? body : null);
    } catch {
      setHeal(null);
    } finally {
      setHealing(false);
    }
  }, []);

  const points = index?.points ?? [];

  const hits: readonly HitAnnotation[] = useMemo(() => {
    if (!search) {
      return [];
    }
    return search.results
      .map((result, position) => ({
        skuId: result.skuId ?? "",
        score: typeof result.score === "number" ? result.score : 0,
        rank: position + 1
      }))
      .filter((hit) => hit.skuId.length > 0);
  }, [search]);

  const healAnnotation: HealAnnotation | null = useMemo(() => {
    if (!heal?.healed || !heal.substituteSkuId) {
      return null;
    }
    return {
      fromSkuId: heal.failedSkuId,
      toSkuId: heal.substituteSkuId,
      cosineScore: heal.cosineScore ?? 0
    };
  }, [heal]);

  const legend = useMemo(() => categoryLegend(points), [points]);
  const selected = points.find((point) => point.skuId === selectedSkuId) ?? null;

  // Reported by the mesh, never assumed. In 'hash' mode fastembed failed to load and the
  // rankings are character overlap, not meaning -- and a panel that showed the same confident
  // scores either way would be the most misleading thing on the dashboard.
  const embeddingMode = search?.embeddingMode ?? heal?.embeddingMode ?? null;
  const degraded = embeddingMode !== null && embeddingMode !== embeddingModeModel;

  return (
    <div className="mx-auto max-w-7xl space-y-4">
      <nav className="flex items-center gap-1 text-[11px] uppercase tracking-wide text-textMuted">
        <Link href="/visualise" className="hover:text-textSecondary transition-colors">
          Visualise
        </Link>
        <ChevronRight className="h-3 w-3" />
        <span className="text-textSecondary">Vector Index</span>
      </nav>

      <header>
        <h2 className="text-headline-sm text-textPrimary">{pageTitle}</h2>
        <p className="mt-1 max-w-3xl text-body-sm text-textSecondary">{pageDescription}</p>
      </header>

      {index && !index.reachable ? (
        <div className="flex items-start gap-2 rounded-lg border border-statusError/30 bg-statusError/10 p-3">
          <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-statusError" />
          <div>
            <div className="text-xs font-semibold text-statusError">Vector index unreachable</div>
            <p className="mt-0.5 font-mono text-[11px] text-textSecondary">{index.detail}</p>
          </div>
        </div>
      ) : null}

      {indexError ? (
        <div className="rounded-lg border border-statusError/30 bg-statusError/10 p-3 font-mono text-[11px] text-statusError">
          {indexError}
        </div>
      ) : null}

      {degraded ? (
        <div className="flex items-start gap-2 rounded-lg border border-statusWarning/30 bg-statusWarning/10 p-3">
          <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-statusWarning" />
          <div className="text-xs text-textSecondary">
            <span className="font-semibold text-statusWarning">Degraded ranking.</span>{" "}
            {search?.rankingQuality ??
              "The embedding model was unavailable, so scores come from a character-hash pseudo-vector and are not semantic similarity."}
          </div>
        </div>
      ) : null}

      <section className={`${panelClass} p-4`}>
        <div className="flex items-center gap-2 pb-3">
          <Database className="h-4 w-4 text-accentPrimary" />
          <h3 className="text-sm font-semibold text-textPrimary">Collection</h3>
          <span className="rounded bg-surfaceContainer px-1.5 py-0.5 font-mono text-[10px] text-textSecondary">
            {index?.collection ?? "…"}
          </span>
          {index?.status ? (
            <span className="rounded border border-statusSuccess/30 bg-statusSuccess/10 px-1.5 py-0.5 font-mono text-[10px] text-statusSuccess">
              {index.status}
            </span>
          ) : null}
        </div>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
          <StatCell label="Points" value={index ? String(index.pointCount) : "…"} />
          <StatCell label="Dimensions" value={index?.dimension ? String(index.dimension) : "…"} />
          <StatCell label="Distance" value={index?.distance ?? "…"} />
          <StatCell label="HNSW m" value={index?.hnswM !== null && index?.hnswM !== undefined ? String(index.hnswM) : "…"} />
          <StatCell
            label="ef_construct"
            value={
              index?.hnswEfConstruct !== null && index?.hnswEfConstruct !== undefined
                ? String(index.hnswEfConstruct)
                : "…"
            }
          />
          <StatCell
            label="Embedding"
            value={embeddingMode ?? "unqueried"}
            hint={embeddingMode === null ? "run a search to find out" : "reported by the mesh"}
          />
        </div>
      </section>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
        <section className={`${panelClass} p-4 lg:col-span-3`}>
          <div className="flex items-center justify-between pb-2">
            <h3 className="text-sm font-semibold text-textPrimary">
              {points.length} embeddings, projected
            </h3>
            {index && index.explainedVariance[0] > 0 ? (
              <span className="font-mono text-[10px] text-textMuted">
                PC1 {(index.explainedVariance[0] * 100).toFixed(1)}% · PC2{" "}
                {(index.explainedVariance[1] * 100).toFixed(1)}% of variance
              </span>
            ) : null}
          </div>

          {/* The caption is not decoration. Without it a viewer reads adjacency in the plane as
              adjacency in the index, and at these variance ratios that is often wrong. */}
          <p className="pb-3 text-[11px] leading-relaxed text-textMuted">
            Each dot is one {index?.dimension ?? 384}-dimensional vector reduced to two principal
            components. The percentages above are how much of the real spread survives the
            reduction — proximity here is suggestive, the cosine scores beside it are the truth.
            Ranking always runs on the full vector.
          </p>

          <div className="aspect-square w-full rounded-md border border-borderSubtle bg-surfaceContainer p-1">
            <VectorIndexMap
              points={points}
              hits={hits}
              heal={healAnnotation}
              selectedSkuId={selectedSkuId}
              onSelect={setSelectedSkuId}
            />
          </div>

          <div className="mt-3 flex flex-wrap gap-x-3 gap-y-1">
            {legend.map((entry) => (
              <span
                key={entry.label}
                className={`flex items-center gap-1 text-[10px] ${
                  entry.isOverflow ? "text-textMuted" : "text-textSecondary"
                }`}
              >
                <span
                  className="inline-block h-2 w-2 rounded-full"
                  style={{ backgroundColor: entry.color }}
                />
                {entry.label}
                <span className="text-textMuted">{entry.count}</span>
              </span>
            ))}
          </div>

          {selected ? (
            <div className="mt-3 rounded-md border border-borderSubtle bg-surfaceContainer p-3">
              <div className="text-xs font-semibold text-textPrimary">{selected.title}</div>
              <div className="mt-1 grid grid-cols-2 gap-x-4 gap-y-1 font-mono text-[11px] text-textSecondary sm:grid-cols-3">
                <span>{selected.skuId}</span>
                <span>{selected.category}</span>
                <span>HSN {selected.hsnCode ?? "—"}</span>
                <span>{formatPaiseToInr(selected.pricePaise)}</span>
                <span>stock {selected.availableStock ?? "—"}</span>
                <span>{selected.brand ?? "—"}</span>
              </div>
              <button
                type="button"
                onClick={() => void runHeal(selected.skuId)}
                disabled={healing}
                className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-borderSubtle bg-bgSurface px-2.5 py-1 text-[11px] font-medium text-textPrimary transition-colors hover:bg-bgSurfaceHover disabled:opacity-50"
              >
                {healing ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <Wand2 className="h-3 w-3 text-statusWarning" />
                )}
                Find a Layer 3 substitute for this SKU
              </button>
            </div>
          ) : (
            <p className="mt-3 text-[11px] text-textMuted">
              Click any point to read its payload and ask Layer 3 for a substitute.
            </p>
          )}
        </section>

        <section className={`${panelClass} flex flex-col p-4 lg:col-span-2`}>
          <h3 className="pb-2 text-sm font-semibold text-textPrimary">Search the index</h3>
          <p className="pb-3 text-[11px] leading-relaxed text-textMuted">
            This posts to the merchant API&apos;s <code className="font-mono">/api/v1/catalog/search</code>{" "}
            — the same route behind the <code className="font-mono">search_catalog</code> MCP tool.
          </p>

          <div className="flex gap-2">
            <input
              value={queryText}
              onChange={(event) => setQueryText(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  void runSearch();
                }
              }}
              placeholder="Describe what you want to buy"
              className="min-w-0 flex-1 rounded-md border border-borderSubtle bg-surfaceContainer px-2.5 py-1.5 text-xs text-textPrimary placeholder:text-textMuted focus:border-accentPrimary focus:outline-none"
            />
            <button
              type="button"
              onClick={() => void runSearch()}
              disabled={searching}
              className="inline-flex shrink-0 items-center gap-1.5 rounded-md bg-accentPrimary px-3 py-1.5 text-xs font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {searching ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Search className="h-3.5 w-3.5" />
              )}
              Search
            </button>
          </div>

          {searchError ? (
            <p className="mt-2 font-mono text-[11px] text-statusError">{searchError}</p>
          ) : null}

          {search ? (
            <div className="mt-3 space-y-1.5">
              {search.results.length === 0 ? (
                <p className="text-[11px] text-textMuted">
                  No results. {search.rankingQuality}
                </p>
              ) : null}
              {search.results.map((result, position) => {
                const score = typeof result.score === "number" ? result.score : 0;
                return (
                  <button
                    key={result.skuId ?? position}
                    type="button"
                    onClick={() => setSelectedSkuId(result.skuId ?? null)}
                    className="flex w-full items-center gap-2 rounded-md border border-borderSubtle bg-surfaceContainer px-2.5 py-1.5 text-left transition-colors hover:bg-bgSurfaceHover"
                  >
                    <span className="font-mono text-[10px] text-textMuted">#{position + 1}</span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[11px] text-textPrimary">
                        {result.title ?? result.skuId}
                      </span>
                      <span className="block truncate font-mono text-[10px] text-textMuted">
                        {result.skuId} · {formatPaiseToInr(result.baseUnitPricePaise)}
                      </span>
                    </span>
                    {/* The bar is the score, not a rank position: the gap between 0.70 and 0.27
                        is the whole story of why one SKU is the answer and the next is noise. */}
                    <span className="flex shrink-0 items-center gap-1.5">
                      <span className="h-1 w-10 overflow-hidden rounded-full bg-borderSubtle">
                        <span
                          className="block h-full rounded-full bg-accentPrimary"
                          style={{ width: `${Math.max(0, Math.min(1, score)) * 100}%` }}
                        />
                      </span>
                      <span className="w-12 text-right font-mono text-[10px] text-textPrimary">
                        {score.toFixed(4)}
                      </span>
                    </span>
                  </button>
                );
              })}
              <p className="pt-1 text-[10px] leading-relaxed text-textMuted">
                {search.rankingQuality}
              </p>
            </div>
          ) : null}

          {heal ? (
            <div className="mt-4 rounded-md border border-borderSubtle bg-surfaceContainer p-3">
              <div className="flex items-center gap-1.5 pb-1.5">
                <Wand2 className="h-3.5 w-3.5 text-statusWarning" />
                <span className="text-xs font-semibold text-textPrimary">Layer 3 substitution</span>
              </div>
              {heal.healed ? (
                <div className="space-y-1 font-mono text-[11px] text-textSecondary">
                  <div>
                    <span className="text-statusError">{heal.failedSkuId}</span>
                    {" → "}
                    <span className="text-statusWarning">{heal.substituteSkuId}</span>
                  </div>
                  <div>cosine {heal.cosineScore?.toFixed(7) ?? "—"}</div>
                  <div>{heal.healingDurationMs.toFixed(2)} ms measured</div>
                </div>
              ) : (
                <p className="font-mono text-[11px] text-textSecondary">
                  Not healed — {heal.reason ?? "no qualifying substitute"}. The 15% price ceiling
                  rejects more candidates than the similarity floor does.
                </p>
              )}
            </div>
          ) : null}
        </section>
      </div>
    </div>
  );
}
