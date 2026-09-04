// Server-side state for a paired agent's delegation.
//
// This is the one stateful surface in an otherwise stateless MCP server, and in custodial mode
// it holds a live buyer signing key. Two consequences shape the design:
//
//   - Mandates live HERE and are referenced by id. The tools never accept a mandate object back
//     from the agent, so a tampered cart is refused at the tool boundary rather than surfacing
//     as an opaque HTTP 400 from the settlement engine.
//   - The TTL is the intent's own validity, and the buyer key is destroyed on settlement, so a
//     signing key cannot outlive the delegation that bounds it.
//
// Redis is used when REDIS_URL is set so that the HTTP transport survives more than one
// process; otherwise an in-process map serves, matching the fallback InMemoryAtomicLocker
// already relied on in inventory/redisLockManager.ts. Which backend answered is reported to
// the agent rather than hidden, because "memory" means the delegation dies with the process.

import type { Redis } from "ioredis";
import type { CartMandate, IntentMandate, UnsignedExecutionPayload } from "@razorpay/agent-buyer-sdk";
import {
  sessionStoreMemory,
  sessionStoreRedis,
  type KeyCustodyMode
} from "../constants/mandateToolConstants.js";
import { millisPerSecond } from "../constants/protocolConstants.js";

export type SessionStoreBackend = typeof sessionStoreRedis | typeof sessionStoreMemory;

export interface DelegationSession {
  readonly delegationId: string;
  readonly userDid: string;
  readonly buyerAgentDid: string;
  readonly keyCustody: KeyCustodyMode;
  readonly intentMandate: IntentMandate;
  readonly expiresAtUnixSeconds: number;
  /** Present only in mesh_demo_custodial mode, and cleared once settlement succeeds. */
  readonly buyerSecretKeyHex?: string;
  readonly cartMandate?: CartMandate;
  readonly cartMandateHash?: string;
  // No merchantAccount. It used to be stored here, described as the reason "settlement cannot be
  // redirected to another account" -- which was never true, because execute_settlement preferred
  // its own `merchant_account` field over this one. The payout destination is now derived from
  // cartMandate.merchantDid by merchant/merchantPayoutRegistry.ts, so there is no session copy to
  // disagree with the signed cart.
  /** The exact payload sign_execution_mandate issued; a signature may only be attached to it. */
  readonly unsignedExecutionPayload?: UnsignedExecutionPayload;
  readonly executionCanonicalJson?: string;
  /**
   * The mandate exactly as it was submitted. Kept so that re-submitting a settlement replays
   * the ORIGINAL signed bundle and is refused by the engine's nonce ledger -- the refusal a
   * judge can trigger themselves. Without it the buyer key has already been destroyed and the
   * replay dies locally with a key error, which proves nothing about the protocol.
   */
  readonly signedExecutionMandate?: Record<string, unknown>;
  readonly settled?: boolean;
}

const sessionKeyPrefix = "mesh:delegation:";
const redisSetExpiryFlag = "EX";

function nowSeconds(): number {
  return Math.floor(Date.now() / millisPerSecond);
}

/**
 * Falls back to an in-process map when Redis is absent. Entries are swept lazily on read
 * rather than by a timer: a session that is never read again does not need collecting, and a
 * timer would keep an idle process alive.
 */
class InMemorySessionStore {
  private readonly _entries = new Map<string, DelegationSession>();

  public get(delegationId: string): DelegationSession | undefined {
    const found = this._entries.get(delegationId);
    if (!found) {
      return undefined;
    }
    if (found.expiresAtUnixSeconds <= nowSeconds()) {
      this._entries.delete(delegationId);
      return undefined;
    }
    return found;
  }

  public set(session: DelegationSession): void {
    this._entries.set(session.delegationId, session);
  }

  public delete(delegationId: string): void {
    this._entries.delete(delegationId);
  }
}

export const defaultInMemorySessionStore = new InMemorySessionStore();

export interface SessionStoreOptions {
  readonly redisClient?: Redis;
}

let cachedRedisClient: Redis | null = null;
let redisResolutionAttempted = false;

/**
 * Resolves a Redis client once per process. A failure is not fatal -- the in-memory store is a
 * working fallback for the single-container demo -- but it is reported, because the difference
 * is visible to the agent as a delegation that will not survive a restart.
 *
 * Exported because the merchant payout registry needs the same client and nothing passes one in:
 * `redisClient` on the options is a test seam, so a second lazy connector there would open a
 * second connection per process to read one key.
 */
export async function resolveSharedRedisClient(): Promise<Redis | null> {
  if (redisResolutionAttempted) {
    return cachedRedisClient;
  }
  redisResolutionAttempted = true;

  const redisUrl = process.env.REDIS_URL;
  if (!redisUrl) {
    return null;
  }
  try {
    const ioredisModule = await import("ioredis");
    const RedisClass = ioredisModule.Redis ?? ioredisModule.default;
    const client = new RedisClass(redisUrl, { maxRetriesPerRequest: null, lazyConnect: false });
    client.on("error", (error: unknown) => {
      process.stderr.write(`Delegation session store Redis error: ${String(error)}\n`);
    });
    cachedRedisClient = client;
  } catch (error: unknown) {
    process.stderr.write(`Delegation session store falling back to memory: ${String(error)}\n`);
    cachedRedisClient = null;
  }
  return cachedRedisClient;
}

/** Which backend this process will use. Reported to the agent on pairing. */
export async function resolveSessionStoreBackend(
  options: SessionStoreOptions = {}
): Promise<SessionStoreBackend> {
  const client = options.redisClient ?? (await resolveSharedRedisClient());
  return client ? sessionStoreRedis : sessionStoreMemory;
}

export async function saveDelegationSession(
  session: DelegationSession,
  options: SessionStoreOptions = {}
): Promise<void> {
  const client = options.redisClient ?? (await resolveSharedRedisClient());
  if (!client) {
    defaultInMemorySessionStore.set(session);
    return;
  }
  const ttlSeconds = Math.max(1, session.expiresAtUnixSeconds - nowSeconds());
  try {
    await client.set(
      `${sessionKeyPrefix}${session.delegationId}`,
      JSON.stringify(session),
      redisSetExpiryFlag,
      ttlSeconds
    );
  } catch (error: unknown) {
    // Writing the session is what makes the next tool call work, so a Redis failure must not
    // lose it silently -- keep it in memory and say so.
    process.stderr.write(`Delegation session Redis write failed, using memory: ${String(error)}\n`);
    defaultInMemorySessionStore.set(session);
  }
}

export async function loadDelegationSession(
  delegationId: string,
  options: SessionStoreOptions = {}
): Promise<DelegationSession | undefined> {
  const client = options.redisClient ?? (await resolveSharedRedisClient());
  if (client) {
    try {
      const raw = await client.get(`${sessionKeyPrefix}${delegationId}`);
      if (raw) {
        return JSON.parse(raw) as DelegationSession;
      }
    } catch (error: unknown) {
      process.stderr.write(`Delegation session Redis read failed: ${String(error)}\n`);
    }
  }
  return defaultInMemorySessionStore.get(delegationId);
}

/**
 * Drops the buyer signing key once it can no longer be needed. Called on successful settlement
 * so that a custodial key's lifetime is the purchase, not the delegation's full 24 hours.
 */
export async function discardSessionBuyerKey(
  session: DelegationSession,
  signedExecutionMandate: Record<string, unknown>,
  options: SessionStoreOptions = {}
): Promise<void> {
  const { buyerSecretKeyHex: _discarded, ...withoutKey } = session;
  await saveDelegationSession(
    { ...withoutKey, signedExecutionMandate, settled: true },
    options
  );
}
