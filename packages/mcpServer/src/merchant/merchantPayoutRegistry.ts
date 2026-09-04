// Resolves where the merchant leg of a settlement is actually paid.
//
// The payout destination used to be a request field. execute_settlement took `merchant_account`
// and handed it to the engine, which handed it to buildSplitManifest, and nothing bound it to
// anything signed: the Cart Mandate carries `merchantDid` but no payout account, so the merchant
// signature attests to the prices and to who is selling and says nothing about where the money
// goes. Any string matching `acc_[A-Za-z0-9_]+` was accepted, and a value passed at settlement
// time silently overrode the one bound when the cart was created. It lands on the mock ledger
// today only because RAZORPAY_ROUTE_LIVE is unset; switching Route transport on would have made
// that a live funds-redirection path for any buyer agent that named its own account.
//
// So the account is derived from the merchant identity the cart was SIGNED with, and a caller can
// only agree with that resolution or be refused. There are exactly two sources, in order:
//
//   1. This mesh's own merchant key. Every cart the mesh signs carries the DID of the key in
//      MERCHANT_PRIVATE_KEY_HEX, and that identity is the demo merchant, so it resolves to
//      defaultMerchantAccount. Derived from the key rather than assumed, so re-keying the mesh
//      moves the DID and the binding follows it.
//   2. A MerchantProfile registered through the Merchant API, read from the Redis key that
//      POST /api/v1/merchant/register writes. This is the branch that makes the resolution a
//      registry lookup rather than a constant -- it is what a second merchant would settle
//      through, and it does not fire in the bundled demo, where the mesh signs every cart itself.
//
// Anything else is refused. An unknown merchant has no payout destination, and inventing one is
// the failure this module exists to prevent.

import type { Redis } from "ioredis";
import { AgentKeyManager } from "@razorpay/agent-buyer-sdk";
import {
  defaultMerchantAccount,
  errorMerchantAccountNotBound,
  errorMerchantPayoutUnregistered,
  razorpayAccountIdRegex,
  redisMerchantProfileKeyPrefix
} from "../constants/mandateToolConstants.js";
import { defaultMerchantPrivateKeyHex } from "../constants/protocolConstants.js";
import { resolveSharedRedisClient } from "../session/delegationSessionStore.js";

export const payoutSourceMeshMerchantKey = "mesh_merchant_key" as const;
export const payoutSourceRegisteredProfile = "registered_profile" as const;

export interface MerchantPayoutAccount {
  /** The merchantDid this account was resolved from -- always a merchant-signed value. */
  readonly merchantDid: string;
  readonly razorpayAccountId: string;
  readonly source: typeof payoutSourceMeshMerchantKey | typeof payoutSourceRegisteredProfile;
}

export interface MerchantRegistryOptions {
  /** Test seam. Nothing passes one in production, so the shared resolver is the real path. */
  readonly redisClient?: Redis;
}

/** The registered account field on merchantApi's MerchantProfile. */
const profileAccountField = "razorpayAccountId";

let cachedMeshMerchantDid: string | undefined;

/**
 * The DID of the key this mesh signs Cart Mandates with.
 *
 * Derived through the same AgentKeyManager.fromSeed the cart tool signs with, so the two cannot
 * disagree about which merchant the mesh is. Memoized because it is a scalar multiplication on a
 * path that runs once per cart and once per settlement.
 */
export function meshMerchantDid(): string {
  cachedMeshMerchantDid ??= AgentKeyManager.fromSeed(defaultMerchantPrivateKeyHex).getAgentDid();
  return cachedMeshMerchantDid;
}

/**
 * Reads a registered merchant's Route account out of the profile the Merchant API stored.
 *
 * Fails closed at every step -- no Redis, no key, unparseable JSON, an account id that is not a
 * Route account id -- because the caller turns `undefined` into a refusal. A payout destination
 * recovered from a damaged record is worse than no payout at all.
 */
async function _readRegisteredProfileAccount(
  merchantDid: string,
  options: MerchantRegistryOptions
): Promise<string | undefined> {
  const client = options.redisClient ?? (await resolveSharedRedisClient());
  if (!client) {
    return undefined;
  }

  let raw: string | null;
  try {
    raw = await client.get(`${redisMerchantProfileKeyPrefix}${merchantDid}`);
  } catch (error: unknown) {
    process.stderr.write(`Merchant profile lookup failed for ${merchantDid}: ${String(error)}\n`);
    return undefined;
  }
  if (!raw) {
    return undefined;
  }

  let accountId: unknown;
  try {
    accountId = (JSON.parse(raw) as Record<string, unknown>)[profileAccountField];
  } catch (error: unknown) {
    process.stderr.write(`Merchant profile for ${merchantDid} is not JSON: ${String(error)}\n`);
    return undefined;
  }
  if (typeof accountId !== "string" || !razorpayAccountIdRegex.test(accountId)) {
    process.stderr.write(
      `Merchant profile for ${merchantDid} carries no usable ${profileAccountField}\n`
    );
    return undefined;
  }
  return accountId;
}

/**
 * The one way a payout destination is chosen. Takes a merchant-signed DID and nothing else, so
 * there is no argument a caller could pass that changes the answer.
 */
export async function resolveMerchantPayoutAccount(
  merchantDid: string,
  options: MerchantRegistryOptions = {}
): Promise<MerchantPayoutAccount> {
  if (merchantDid === meshMerchantDid()) {
    return {
      merchantDid,
      razorpayAccountId: defaultMerchantAccount,
      source: payoutSourceMeshMerchantKey
    };
  }

  const registered = await _readRegisteredProfileAccount(merchantDid, options);
  if (registered) {
    return { merchantDid, razorpayAccountId: registered, source: payoutSourceRegisteredProfile };
  }
  throw new Error(errorMerchantPayoutUnregistered(merchantDid));
}

/**
 * Holds a supplied `merchant_account` to the resolved one.
 *
 * The field is kept on both tools rather than dropped so that a caller which means to redirect a
 * payout gets a refusal naming the rule, instead of having the argument stripped by the schema
 * and being told the purchase succeeded. Omitting it is always correct.
 */
export function assertRequestedMerchantAccountMatches(
  requested: string | undefined,
  resolved: MerchantPayoutAccount
): void {
  if (requested === undefined || requested === resolved.razorpayAccountId) {
    return;
  }
  throw new Error(
    errorMerchantAccountNotBound(requested, resolved.razorpayAccountId, resolved.merchantDid)
  );
}
