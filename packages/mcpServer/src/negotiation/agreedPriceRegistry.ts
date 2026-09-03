// The negotiated prices this mesh has agreed to, so a converged bargain reaches the bill.
//
// Before this, negotiate_price converged, recorded the agreement in the gateway's contract AST,
// and changed nothing: get_live_sku_quote priced from the catalog, and the cart re-derived the
// same list-based figure. Across a 44-run rehearsal nine negotiations converged and the realised
// saving was zero on all nine, while one agent told its user it had saved 661.50 rupees.
//
// The fix does NOT touch the quote hash. cartMandateCreator re-runs executeSkuQuote and compares,
// which is the property that stops an agent naming its own price -- so the agreement has to be
// something the mesh looks up for itself on both passes, exactly like a merchant's promotion.
// That is all this is: a short-lived, buyer-scoped price the quoter consults.
//
// Only the negotiation loop writes here, and only after the x402 gateway reports convergence.
// Nothing an agent sends can put a price in this map.
//
// An agreement is not consumed by a purchase. It lapses. Repeat buys inside the window are
// bounded by the session purchase guard, and every one of them is still above the merchant's
// margin floor -- the gateway clamps the seller's ask there, so a bindable price cannot be a
// giveaway. Honouring the agreement once and then quietly reverting to list would be the more
// surprising behaviour of the two.
//
// State is in-process, matching IssuedQuoteRegistry and InMemoryAtomicLocker: the negotiation,
// the quote and the cart are always served by the same mcpServer process. Replicating the server
// means moving these records to Redis beside the lock records.

import { agreedPriceValiditySeconds } from "../constants/negotiationConstants.js";
import { millisPerSecond } from "../constants/protocolConstants.js";

export interface AgreedPriceLookup {
  readonly skuId: string;
  readonly quantity: number;
  readonly buyerAgentId: string;
}

export interface AgreedPrice extends AgreedPriceLookup {
  readonly agreedUnitPricePaise: number;
  readonly contractAstHash: string | null;
  readonly agreementExpiresAt: number;
}

export function currentUnixSeconds(): number {
  return Math.floor(Date.now() / millisPerSecond);
}

/**
 * Scoped to the exact purchase that was bargained for.
 *
 * The buyer agent DID is part of the key because a negotiation is a private agreement: one
 * agent's bargain must not become another's price. The quantity is part of it because the
 * gateway compiles its contract AST for that quantity, and a unit price agreed for twelve is
 * not an offer on one.
 */
function agreementKey(lookup: AgreedPriceLookup): string {
  return `${lookup.buyerAgentId}|${lookup.skuId}|${lookup.quantity}`;
}

export class AgreedPriceRegistry {
  private readonly agreementsByKey = new Map<string, AgreedPrice>();

  /** Called by negotiate_price when, and only when, the gateway reports CONVERGED. */
  public record(
    agreement: Omit<AgreedPrice, "agreementExpiresAt">,
    nowUnix: number = currentUnixSeconds()
  ): AgreedPrice {
    this._forgetLapsed(nowUnix);
    const stored: AgreedPrice = {
      ...agreement,
      agreementExpiresAt: nowUnix + agreedPriceValiditySeconds
    };
    this.agreementsByKey.set(agreementKey(stored), stored);
    return stored;
  }

  /** Consulted by get_live_sku_quote on the agent's pass and again on the cart's re-quote. */
  public lookup(
    requested: AgreedPriceLookup,
    nowUnix: number = currentUnixSeconds()
  ): AgreedPrice | undefined {
    const agreement = this.agreementsByKey.get(agreementKey(requested));
    if (!agreement || agreement.agreementExpiresAt < nowUnix) {
      return undefined;
    }
    return agreement;
  }

  public get size(): number {
    return this.agreementsByKey.size;
  }

  /** Test seam. Production never clears the registry. */
  public clear(): void {
    this.agreementsByKey.clear();
  }

  /**
   * Dropped on write rather than on a timer, as in IssuedQuoteRegistry: a lapsed agreement can
   * never be looked up again, so the map holds at most the last few minutes of bargains.
   */
  private _forgetLapsed(nowUnix: number): void {
    for (const [key, agreement] of this.agreementsByKey) {
      if (agreement.agreementExpiresAt < nowUnix) {
        this.agreementsByKey.delete(key);
      }
    }
  }
}

export const defaultAgreedPriceRegistry = new AgreedPriceRegistry();
