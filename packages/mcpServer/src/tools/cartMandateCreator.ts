// create_cart_mandate -- turns a delegation plus a live quote and a live lock into a
// merchant-signed Cart Mandate (M_C).
//
// The mesh RE-DERIVES every number here rather than accepting figures relayed by the agent.
// That is the whole defence: the merchant key signs this document, so the merchant must only
// attest to prices the merchant produced. Accepting agent-supplied prices would still pass
// validateBudgetGate, because the enclave only checks internal consistency -- it has no way to
// know what the real price was.

import { AgentKeyManager, createSignedCartMandate, computeMandateHash } from "@razorpay/agent-buyer-sdk";
import {
  cartDiscountPaise,
  cartDiscountRationale,
  defaultMerchantAccount,
  demoMerchantGstin,
  demoMerchantStateCode,
  errorDelegationAlreadySettled,
  errorLockSignatureInvalid,
  errorQuoteExpired,
  errorQuoteMismatch,
  errorUnknownDelegation,
  errorUnserviceableAddress
} from "../constants/mandateToolConstants.js";
import {
  defaultMerchantPrivateKeyHex,
  defaultOriginPincode,
  millisPerSecond,
  quoteExpiryGraceSeconds,
  quoteValiditySeconds
} from "../constants/protocolConstants.js";
import {
  createCartMandateRequestSchema,
  type CreateCartMandateRequest
} from "../schemas/createCartMandateSchema.js";
import { executeSkuQuote } from "./skuQuoter.js";
import { verifyShippingSla } from "./slaVerifier.js";
import { verifyQuoteHash } from "../crypto/quoteHashSigner.js";
import { verifyLockSignature } from "../crypto/lockSignatureGenerator.js";
import {
  loadDelegationSession,
  saveDelegationSession,
  type DelegationSession,
  type SessionStoreOptions
} from "../session/delegationSessionStore.js";

/**
 * Re-quotes and compares. `verifyQuoteHash` is HMAC over the same fields the quote tool signed,
 * so a match proves the agent is carrying a quote this mesh issued for these exact parameters
 * -- not a price it invented or an older, cheaper one.
 */
function reconcileQuote(request: CreateCartMandateRequest, buyerAgentDid: string) {
  const quote = executeSkuQuote({
    sku_id: request.sku_id,
    quantity: request.quantity,
    buyer_agent_id: buyerAgentDid,
    delivery_pincode: request.delivery_pincode,
    promo_code: request.promo_code
  });

  const nowSeconds = Math.floor(Date.now() / millisPerSecond);
  const hashMatchesAt = (expiry: number): boolean =>
    verifyQuoteHash(
      {
        skuId: quote.sku_id,
        quantity: request.quantity,
        offeredUnitPricePaise: quote.offered_unit_price_paise,
        totalTaxPaise: quote.tax_breakdown.total_tax_paise,
        quoteExpiryTimestamp: expiry,
        buyerAgentId: buyerAgentDid
      },
      request.quote_hash
    );

  // The agent passed the expiry back, so there is nothing to search for: one hash check settles
  // whether the parameters agree, and the timestamp itself settles whether the quote is still live.
  if (request.quote_expiry_timestamp !== undefined) {
    if (!hashMatchesAt(request.quote_expiry_timestamp)) {
      throw new Error(errorQuoteMismatch);
    }
    _rejectIfLapsed(request.quote_expiry_timestamp, nowSeconds);
    return quote;
  }

  // No expiry supplied. quoteExpiryTimestamp is the only free variable in the HMAC payload
  // (quoteHashSigner.ts), so scanning it recovers the exact timestamp the quote was signed with
  // -- which is what separates "these parameters never matched" from "they matched, and then the
  // quote lapsed". Scanning below `now` as well as above is the whole point: the old loop started
  // at now-2 and so could never see an expired quote, and reported every one as a hash mismatch.
  const earliest = nowSeconds - quoteValiditySeconds - quoteExpiryGraceSeconds;
  const latest = nowSeconds + quoteValiditySeconds + quoteExpiryGraceSeconds;
  let matchedExpiry: number | undefined;
  for (let expiry = latest; expiry >= earliest; expiry--) {
    if (hashMatchesAt(expiry)) {
      matchedExpiry = expiry;
      break;
    }
  }
  if (matchedExpiry === undefined) {
    throw new Error(errorQuoteMismatch);
  }
  _rejectIfLapsed(matchedExpiry, nowSeconds);
  return quote;
}

/**
 * Refuses a quote whose expiry has passed, grace included. Separated so both reconciliation
 * paths above produce the identical refusal.
 */
function _rejectIfLapsed(quoteExpiryTimestamp: number, nowSeconds: number): void {
  if (quoteExpiryTimestamp >= nowSeconds - quoteExpiryGraceSeconds) {
    return;
  }
  throw new Error(errorQuoteExpired(nowSeconds - quoteExpiryTimestamp, quoteValiditySeconds));
}

/**
 * Confirms the lock is one this mesh minted, without a lock lookup: reserve_inventory_lock
 * already returned the merchant signature over exactly these five fields.
 */
function reconcileLock(request: CreateCartMandateRequest): void {
  const valid = verifyLockSignature(
    {
      lockToken: request.lock_token,
      fencingToken: request.fencing_token,
      skuId: request.sku_id,
      quantityLocked: request.quantity,
      expiresAtUnixMs: request.lock_expires_at_unix_ms
    },
    request.lock_signature
  );
  if (!valid) {
    throw new Error(errorLockSignatureInvalid);
  }
}

export async function createCartMandateForDelegation(
  rawRequest: unknown,
  options: SessionStoreOptions = {}
): Promise<Record<string, unknown>> {
  const request = createCartMandateRequestSchema.parse(rawRequest);
  const session = await loadDelegationSession(request.delegation_id, options);
  if (!session) {
    throw new Error(errorUnknownDelegation);
  }
  // Before reconcileQuote, so a spent delegation costs the agent one refusal rather than a quote
  // and a cart. The inventory lock is taken one tool earlier by reserve_inventory_lock, which
  // carries no delegation_id, so that reservation is still held until its TTL sweeps it.
  if (session.settled) {
    throw new Error(errorDelegationAlreadySettled);
  }

  const quote = reconcileQuote(request, session.buyerAgentDid);
  reconcileLock(request);

  const sla = verifyShippingSla({
    origin_pincode: defaultOriginPincode,
    delivery_pincode: request.delivery_pincode,
    package_weight_grams: request.package_weight_grams
  });
  // The SLA tool reports an unserviceable address rather than raising, so the cart tool is where
  // that answer has to become a refusal -- otherwise the merchant signs a cart for a delivery no
  // courier will accept, and the reason reaches the agent only as a settlement failure.
  if (!sla.serviceable) {
    throw new Error(`${errorUnserviceableAddress} ${sla.unserviceable_reason ?? ""}`.trim());
  }

  return _signAndStoreCart({ request, session, quote, sla, options });
}

interface SignCartParams {
  readonly request: CreateCartMandateRequest;
  readonly session: DelegationSession;
  readonly quote: ReturnType<typeof executeSkuQuote>;
  readonly sla: ReturnType<typeof verifyShippingSla>;
  readonly options: SessionStoreOptions;
}

async function _signAndStoreCart(params: SignCartParams): Promise<Record<string, unknown>> {
  const { request, session, quote, sla } = params;

  // Tax is floored PER LINE by the pricing engine. Recomputing it from the subtotal here can
  // differ by a paise and fail ArithmeticEnclaveMismatchException at settlement.
  const lineTotalPaise = quote.offered_unit_price_paise * request.quantity;
  const totalTaxPaise = quote.tax_breakdown.total_tax_paise;
  const totalPaise = lineTotalPaise + totalTaxPaise + sla.shipping_cost_paise;

  // SECONDS, deliberately. The engine's _verifyInventoryLockActive compares this against
  // int(time.time()); passing the lock tool's milliseconds makes `evaluatedAt > expiresAt`
  // always false, so the guard cannot fire and an expired reservation still settles -- stock
  // released back to other buyers gets sold twice. The dashboard driver emits seconds too.
  const inventoryLockExpiresAt = Math.floor(request.lock_expires_at_unix_ms / millisPerSecond);

  const merchantSigner = AgentKeyManager.fromSeed(defaultMerchantPrivateKeyHex);
  const cartMandate = createSignedCartMandate(
    {
      merchantGstin: demoMerchantGstin,
      merchantStateCode: demoMerchantStateCode,
      buyerDeliveryPincode: request.delivery_pincode,
      buyerDeliveryStateCode: request.delivery_state_code,
      items: [
        {
          skuId: quote.sku_id,
          quantity: request.quantity,
          unitPricePaise: quote.offered_unit_price_paise,
          hsnCode: quote.hsn_code,
          gstRatePercent: quote.gst_rate_percent,
          lineTotalPaise,
          // From the re-quote above, never from the request: `reconcileQuote` recomputes the
          // quote server-side, so this is the mesh's own classification of the SKU rather than
          // one the agent could choose to match its delegation.
          category: quote.category
        }
      ],
      taxableSubtotalPaise: lineTotalPaise,
      taxBreakdown: {
        cgstPaise: quote.tax_breakdown.cgst_paise,
        sgstPaise: quote.tax_breakdown.sgst_paise,
        igstPaise: quote.tax_breakdown.igst_paise,
        totalTaxPaise
      },
      shippingPaise: sla.shipping_cost_paise,
      discountPaise: cartDiscountPaise,
      totalPaise,
      inventoryLockToken: request.lock_token,
      inventoryLockExpiresAt
    },
    merchantSigner
  );

  const cartMandateHash = computeMandateHash(cartMandate as unknown as Record<string, unknown>);
  // Drop any settled-purchase state rather than spreading it onto the new cart. Carrying
  // `settled` forward would re-arm the guard above against a session that is starting a fresh
  // purchase; carrying `signedExecutionMandate` forward is worse, because settlementExecutor
  // prefers a stored signed bundle over building one, and its execution_id guard inspects
  // unsignedExecutionPayload -- which IS refreshed -- so a stale mandate would pass that check
  // and settle the PREVIOUS purchase against this new cart. The guard above makes this
  // unreachable today; this keeps it unreachable if the guard ever moves.
  const {
    settled: _settled,
    signedExecutionMandate: _signedExecutionMandate,
    ...carriedForward
  } = session;
  await saveDelegationSession(
    { ...carriedForward, cartMandate, cartMandateHash, merchantAccount: request.merchant_account },
    params.options
  );

  return {
    cart_mandate: cartMandate,
    cart_mandate_hash: cartMandateHash,
    total_paise: totalPaise,
    taxable_subtotal_paise: lineTotalPaise,
    tax_breakdown: quote.tax_breakdown,
    shipping_fee_paise: sla.shipping_cost_paise,
    discount_paise: cartDiscountPaise,
    discount_rationale: cartDiscountRationale,
    inventory_lock_expires_at: inventoryLockExpiresAt,
    inventory_lock_expires_at_unit: "unix_seconds",
    merchant_did: cartMandate.merchantDid,
    price_reconciled: true
  };
}
