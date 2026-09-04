// GET /api/mesh/vectors -> the catalog's vector index, projected for drawing.
//
// Reads Qdrant directly rather than asking the merchant API what is in it. The merchant API is
// the writer; if the map were drawn from the writer's own account of its work it could not show
// a listing that failed to index, which is the one failure a vector-index panel exists to catch.
//
// The browser cannot reach Qdrant itself -- inside Docker it resolves by compose service name,
// and exposing a database port to the page would be a poor idea in any case -- so the hop is
// server-side, and the 384-dimensional vectors are reduced here rather than shipped to the
// client. 64 points x 384 floats is about 200 KB of JSON that nothing on the page would use.

import { resolveServiceUrls } from "@/server/protocolDriver/driverConfig";
import { projectToPlane } from "@/lib/vectorProjection";
import type { VectorIndexPoint, VectorIndexResponse } from "@/types/vectorIndexTypes";
import {
  catalogCollectionName,
  vectorScrollPageSize,
  vectorUpstreamTimeoutMs
} from "@/constants/vectorIndexConstants";

export const runtime = "nodejs";
// The collection changes whenever a merchant publishes, so a cached projection would show a
// catalog that no longer exists.
export const dynamic = "force-dynamic";

interface QdrantPoint {
  readonly id: number | string;
  readonly vector?: number[] | Record<string, number[]>;
  readonly payload?: Record<string, unknown>;
}

interface QdrantScrollResponse {
  readonly result?: {
    readonly points?: QdrantPoint[];
    readonly next_page_offset?: number | string | null;
  };
}

interface QdrantCollectionResponse {
  readonly result?: {
    readonly points_count?: number;
    readonly indexed_vectors_count?: number;
    readonly status?: string;
    readonly config?: {
      readonly params?: {
        readonly vectors?: { readonly size?: number; readonly distance?: string };
      };
      readonly hnsw_config?: { readonly m?: number; readonly ef_construct?: number };
    };
  };
}

function readString(payload: Record<string, unknown>, key: string): string | null {
  const value = payload[key];
  return typeof value === "string" && value.length > 0 ? value : null;
}

function readNumber(payload: Record<string, unknown>, key: string): number | null {
  const value = payload[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

/**
 * Qdrant returns either a bare array (single unnamed vector) or a map of named vectors.
 * This collection is configured with one unnamed vector, but reading defensively costs a line
 * and means a later named-vector migration degrades to an empty map rather than a crash.
 */
function extractVector(point: QdrantPoint): number[] | null {
  if (Array.isArray(point.vector)) {
    return point.vector;
  }
  if (point.vector && typeof point.vector === "object") {
    const first = Object.values(point.vector)[0];
    return Array.isArray(first) ? first : null;
  }
  return null;
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    signal: AbortSignal.timeout(vectorUpstreamTimeoutMs)
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText} from ${url}`);
  }
  return (await response.json()) as T;
}

/**
 * Pages the whole collection.
 *
 * Bounded by the page size rather than a total cap: a partial map is worse than a slow one,
 * because a SKU missing from the picture reads as a SKU missing from the index.
 */
async function scrollAllPoints(qdrantUrl: string): Promise<QdrantPoint[]> {
  const collected: QdrantPoint[] = [];
  let offset: number | string | null = null;

  for (;;) {
    const body: Record<string, unknown> = {
      limit: vectorScrollPageSize,
      with_payload: true,
      with_vector: true
    };
    if (offset !== null) {
      body.offset = offset;
    }

    const page = await fetchJson<QdrantScrollResponse>(
      `${qdrantUrl}/collections/${catalogCollectionName}/points/scroll`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      }
    );

    collected.push(...(page.result?.points ?? []));
    offset = page.result?.next_page_offset ?? null;
    if (offset === null || offset === undefined) {
      return collected;
    }
  }
}

export async function GET(): Promise<Response> {
  const { qdrantUrl } = resolveServiceUrls();

  let collection: QdrantCollectionResponse;
  let rawPoints: QdrantPoint[];
  try {
    collection = await fetchJson<QdrantCollectionResponse>(
      `${qdrantUrl}/collections/${catalogCollectionName}`
    );
    rawPoints = await scrollAllPoints(qdrantUrl);
  } catch (error: unknown) {
    // An unreachable index is reported as unreachable. An empty map with no explanation would
    // read as "the catalog is not indexed", which is a different and more alarming claim.
    const detail = error instanceof Error ? error.message : String(error);
    const body: VectorIndexResponse = {
      collection: catalogCollectionName,
      reachable: false,
      status: null,
      pointCount: 0,
      indexedVectorCount: null,
      dimension: null,
      distance: null,
      hnswM: null,
      hnswEfConstruct: null,
      explainedVariance: [0, 0],
      points: [],
      detail
    };
    return Response.json(body, { status: 200 });
  }

  const withVectors = rawPoints
    .map((point) => ({ point, vector: extractVector(point) }))
    .filter((entry): entry is { point: QdrantPoint; vector: number[] } => entry.vector !== null);

  const projection = projectToPlane(withVectors.map((entry) => entry.vector));

  const points: VectorIndexPoint[] = withVectors.map((entry, index) => {
    const payload = entry.point.payload ?? {};
    const projected = projection.points[index];
    return {
      pointId: String(entry.point.id),
      skuId: readString(payload, "skuId") ?? String(entry.point.id),
      title: readString(payload, "title") ?? "(untitled listing)",
      brand: readString(payload, "brand"),
      category: readString(payload, "category") ?? "uncategorised",
      pricePaise: readNumber(payload, "baseUnitPricePaise"),
      availableStock: readNumber(payload, "availableStock"),
      hsnCode: readString(payload, "hsnCode"),
      x: projected?.x ?? 0.5,
      y: projected?.y ?? 0.5
    };
  });

  const params = collection.result?.config?.params?.vectors;
  const body: VectorIndexResponse = {
    collection: catalogCollectionName,
    reachable: true,
    status: collection.result?.status ?? null,
    pointCount: collection.result?.points_count ?? points.length,
    indexedVectorCount: collection.result?.indexed_vectors_count ?? null,
    dimension: params?.size ?? projection.dimension,
    distance: params?.distance ?? null,
    hnswM: collection.result?.config?.hnsw_config?.m ?? null,
    hnswEfConstruct: collection.result?.config?.hnsw_config?.ef_construct ?? null,
    explainedVariance: projection.explainedVariance,
    points
  };

  return Response.json(body, { status: 200 });
}
