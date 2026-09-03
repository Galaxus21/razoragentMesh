// Keeps the in-process catalog in step with what merchants publish.
//
// Extracted from mcpServerMain.ts, which had grown past the 300-line limit once the tool layer
// started publishing telemetry. This is Redis wiring and has nothing to do with JSON-RPC, so it
// is the natural piece to lift out; behaviour is unchanged.
//
// Two Redis clients are needed, not one: a connection in subscriber mode cannot issue SCAN or
// MGET, so boot-time hydration gets its own.

import { hydrateCatalogFromRedis } from "./catalogHydrator.js";
import { defaultCatalogStore } from "./catalogStore.js";

const subscriberModeErrorFragment = "Connection in subscriber mode";
const retryBackoffStepMs = 100;
const retryBackoffCeilingMs = 2000;

const catalogSubscriberDisabledWarning =
  "[MCP Warning] REDIS_URL is unset; serving the compiled catalog fixtures only. SKUs "
  + "published from the Merchant Studio will NOT appear until this server is restarted "
  + "with REDIS_URL set.\n";

/**
 * Subscribes to merchant catalog updates and hydrates from Redis.
 *
 * A missing REDIS_URL is not an error: the server ships compiled catalog fixtures and stays
 * fully serviceable without Redis, so it declines to subscribe rather than failing to start.
 *
 * It does say so, though. Returning in silence made the degraded mode invisible: SKUs published
 * through the Merchant Studio simply stopped propagating, and the symptom -- a catalog that is
 * stale but not empty -- points nowhere near the cause. One line at startup is the difference
 * between a five-minute diagnosis and an afternoon.
 */
export function initializeCatalogSubscriber(redisUrl?: string): void {
  const targetUrl = redisUrl ?? process.env.REDIS_URL;
  if (!targetUrl) {
    process.stderr.write(catalogSubscriberDisabledWarning);
    return;
  }
  import("ioredis")
    .then((ioredisModule) => {
      const RedisClass = ioredisModule.Redis ?? ioredisModule.default;
      const subscriber = new RedisClass(targetUrl, {
        retryStrategy: (times: number) =>
          Math.min(times * retryBackoffStepMs, retryBackoffCeilingMs),
        maxRetriesPerRequest: null,
        enableOfflineQueue: true,
        lazyConnect: false
      });
      subscriber.on("error", (error: unknown) => {
        const msg = String(error);
        if (!msg.includes(subscriberModeErrorFragment)) {
          process.stderr.write("Redis pub/sub subscriber error: " + msg + "\n");
        }
      });
      defaultCatalogStore.subscribeToCatalogChannel(subscriber);

      // Hydration runs after the subscription is established, so a change published mid-scan
      // is applied by the subscriber rather than lost between the two.
      const reader = new RedisClass(targetUrl, {
        maxRetriesPerRequest: null,
        lazyConnect: false
      });
      hydrateCatalogFromRedis(defaultCatalogStore, reader)
        .then((loadedCount: number) => {
          if (loadedCount > 0) {
            process.stderr.write(`Catalog hydrated from Redis: ${loadedCount} SKU(s)\n`);
          }
        })
        .catch((error: unknown) => {
          // The compiled fixtures remain serviceable, so this is reported and not fatal.
          process.stderr.write("Catalog hydration skipped: " + String(error) + "\n");
        });
    })
    .catch((error: unknown) => {
      process.stderr.write("Redis pub/sub subscriber error: " + String(error) + "\n");
    });
}
