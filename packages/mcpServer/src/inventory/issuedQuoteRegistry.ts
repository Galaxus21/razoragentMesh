// The quotes this mesh has actually issued, so an inventory lock can refuse a hash it never made.
//
// reserve_inventory_lock requires a quote_hash and used to fold it straight into the lock
// signature without checking it. A fabricated hash therefore produced a real lock that consumed
// real stock, and the mistake surfaced two tools later at create_cart_mandate, which re-derives
// the price and compares. Nothing could be BOUGHT at a wrong price -- but the mesh took inventory
// on a claim it had not verified, and the agent learned late, holding a lock it could not use.
//
// The locker cannot re-derive the hash itself. computeQuoteHash covers the tax total, which
// depends on the delivery pincode, and reserve_inventory_lock is not given one -- so unlike
// cartMandateCreator, which has the pincode and brute-forces the one remaining free variable,
// there is nothing here to reconcile against. The quoter therefore records what it issued and the
// locker looks it up.
//
// State is in-process, matching InMemoryAtomicLocker in redisLockManager.ts: a quote and the lock
// that follows it are always served by the same mcpServer process here, over MCP and over the
// REST adapter alike. Replicating the server means moving these records to Redis beside the lock
// records, or one replica would refuse a quote its sibling issued.

import {
  millisPerSecond,
  quoteExpiryGraceSeconds,
  quoteValiditySeconds
} from "../constants/protocolConstants.js";

export interface IssuedQuote {
  readonly quoteHash: string;
  readonly skuId: string;
  readonly quantity: number;
  readonly buyerAgentId: string;
  readonly quoteExpiryTimestamp: number;
}

export interface IssuedQuoteLookup {
  readonly quoteHash: string;
  readonly skuId: string;
  readonly quantity: number;
  readonly buyerAgentId: string;
}

/**
 * Why a quote_hash was refused. Kept distinct for the same reason errorQuoteExpired is distinct
 * from errorQuoteMismatch: an agent told "hash mismatch" goes hunting for a hashing bug, when the
 * real instruction is either "quote first", "quote again" or "you are locking the wrong thing".
 */
export type IssuedQuoteVerdict =
  | { readonly outcome: "issued"; readonly issued: IssuedQuote }
  | { readonly outcome: "unknown" }
  | { readonly outcome: "expired"; readonly issued: IssuedQuote; readonly lapsedSeconds: number }
  | { readonly outcome: "parametersDiffer"; readonly issued: IssuedQuote };

// Agent-facing refusals live here rather than in mandateToolConstants because this guard is the
// only thing that raises them, and only err.message reaches the agent.
export const errorQuoteNotIssued =
  "quote_hash is not a quote this mesh issued. Call get_live_sku_quote for this SKU, quantity " +
  "and buyer_agent_id first, then pass the quote_hash it returns through unchanged. An inventory " +
  "lock is only granted against a live quote, so no stock has been reserved.";

export const errorQuoteLapsedBeforeLock = (lapsedSecondsAgo: number): string =>
  `quote expired ${lapsedSecondsAgo}s ago; quotes are valid for ${quoteValiditySeconds}s. The ` +
  "hash was one this mesh issued -- only the clock moved. Call get_live_sku_quote again and " +
  "retry reserve_inventory_lock with the fresh quote_hash. No stock has been reserved.";

export const errorQuoteCoversDifferentPurchase = (
  issued: IssuedQuote,
  requested: IssuedQuoteLookup
): string =>
  `quote_hash was issued for ${issued.quantity} x ${issued.skuId} for ${issued.buyerAgentId}, ` +
  `but you asked to lock ${requested.quantity} x ${requested.skuId} for ` +
  `${requested.buyerAgentId}. A quote is bound to the exact purchase it priced. Call ` +
  "get_live_sku_quote for what you actually want to lock. No stock has been reserved.";

export class IssuedQuoteRegistry {
  private readonly issuedByHash = new Map<string, IssuedQuote>();

  /** Called by get_live_sku_quote for every hash it hands out. */
  public record(quote: IssuedQuote, nowUnix: number = currentUnixSeconds()): void {
    this._forgetLapsed(nowUnix);
    this.issuedByHash.set(quote.quoteHash, quote);
  }

  public verify(
    requested: IssuedQuoteLookup,
    nowUnix: number = currentUnixSeconds()
  ): IssuedQuoteVerdict {
    const issued = this.issuedByHash.get(requested.quoteHash);
    if (!issued) {
      return { outcome: "unknown" };
    }
    // Grace matches cartMandateCreator's, so a quote does not become lockable and unusable, or
    // usable and unlockable, in the two seconds between the two guards.
    if (issued.quoteExpiryTimestamp < nowUnix - quoteExpiryGraceSeconds) {
      return { outcome: "expired", issued, lapsedSeconds: nowUnix - issued.quoteExpiryTimestamp };
    }
    if (
      issued.skuId !== requested.skuId ||
      issued.quantity !== requested.quantity ||
      issued.buyerAgentId !== requested.buyerAgentId
    ) {
      return { outcome: "parametersDiffer", issued };
    }
    return { outcome: "issued", issued };
  }

  public get size(): number {
    return this.issuedByHash.size;
  }

  /** Test seam. Production never clears the registry. */
  public clear(): void {
    this.issuedByHash.clear();
  }

  /**
   * Dropped on write rather than on a timer: a lapsed quote can never be verified again, so the
   * map holds at most the quotes of the last minute and a sweeper would be machinery for nothing.
   */
  private _forgetLapsed(nowUnix: number): void {
    const oldestUsable = nowUnix - quoteExpiryGraceSeconds;
    for (const [hash, quote] of this.issuedByHash) {
      if (quote.quoteExpiryTimestamp < oldestUsable) {
        this.issuedByHash.delete(hash);
      }
    }
  }
}

export function currentUnixSeconds(): number {
  return Math.floor(Date.now() / millisPerSecond);
}

export const defaultIssuedQuoteRegistry = new IssuedQuoteRegistry();
