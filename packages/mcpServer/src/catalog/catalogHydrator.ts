// Loads the merchant catalog out of Redis at startup.
//
// The store previously learned about merchant SKUs only from the `mesh:catalog:updates` pub/sub
// channel, which carries changes and not state. Two consequences followed. A restarted mcpServer
// silently forgot every SKU a merchant had ever published and fell back to the compiled-in
// fixtures. And `scripts/seedCatalog.py`, which writes the stores directly, produced 25 SKUs that
// the protocol path could never quote -- the seeder cannot announce them over pub/sub either,
// because nothing guarantees a subscriber exists at the moment it runs.
//
// Reading the keys at boot fixes both: the catalog becomes the compiled fixtures merged with
// whatever Redis currently holds, and the pub/sub subscription goes back to doing only what it is
// good at, which is applying changes after that point.

import { meshCatalogKeyPrefix, meshCatalogUpdatesChannel } from "../constants/protocolConstants.js";
import { CatalogSkuItem } from "../types/mcpToolTypes.js";
import { CatalogStore } from "./catalogStore.js";

const scanMatchArgument = "MATCH" as const;
const scanCountArgument = "COUNT" as const;

// Narrowed to exactly the one overload this module calls, so an ioredis client satisfies it
// structurally without the whole Redis surface having to be modelled here.
export interface RedisCatalogReader {
  scan(
    cursor: string,
    matchToken: typeof scanMatchArgument,
    pattern: string,
    countToken: typeof scanCountArgument,
    count: number
  ): Promise<[string, string[]]>;
  mget(...keys: string[]): Promise<(string | null)[]>;
}
const scanBatchSize = 200;
const scanStartCursor = "0";

// The merchant API writes `title`; CatalogSkuItem calls the same field `name`. Accepting both
// here keeps the seeder fixtures usable without rewriting a file the Python side also reads.
export function normalizeCatalogRecord(rawRecord: unknown): CatalogSkuItem | null {
  if (typeof rawRecord !== "object" || rawRecord === null) {
    return null;
  }
  const record = rawRecord as Record<string, unknown>;
  const resolvedName = record.name ?? record.title;
  if (typeof resolvedName !== "string" || resolvedName.length === 0) {
    return null;
  }
  return { ...record, name: resolvedName } as unknown as CatalogSkuItem;
}

async function scanCatalogKeys(redisReader: RedisCatalogReader): Promise<string[]> {
  const discovered: string[] = [];
  let cursor = scanStartCursor;
  do {
    const [nextCursor, batch] = await redisReader.scan(
      cursor,
      scanMatchArgument,
      `${meshCatalogKeyPrefix}*`,
      scanCountArgument,
      scanBatchSize
    );
    cursor = nextCursor;
    // The pub/sub channel shares the prefix but is not a key; skip it if it ever becomes one.
    discovered.push(...batch.filter((key) => key !== meshCatalogUpdatesChannel));
  } while (cursor !== scanStartCursor);
  return discovered;
}

/**
 * Merges every `mesh:catalog:*` record into the store. Returns how many were applied.
 *
 * A malformed record is skipped rather than thrown, because one bad payload written by an older
 * merchant build must not stop the server from serving the rest of the catalog.
 */
export async function hydrateCatalogFromRedis(
  store: CatalogStore,
  redisReader: RedisCatalogReader
): Promise<number> {
  const catalogKeys = await scanCatalogKeys(redisReader);
  if (catalogKeys.length === 0) {
    return 0;
  }

  const payloads = await redisReader.mget(...catalogKeys);
  let appliedCount = 0;
  for (const payload of payloads) {
    if (typeof payload !== "string" || payload.length === 0) {
      continue;
    }
    try {
      const candidate = normalizeCatalogRecord(JSON.parse(payload));
      if (!candidate) {
        continue;
      }
      store.addSku(candidate);
      appliedCount += 1;
    } catch {
      // Unparseable JSON or a record the schema rejects: skip it and keep going.
    }
  }
  return appliedCount;
}
