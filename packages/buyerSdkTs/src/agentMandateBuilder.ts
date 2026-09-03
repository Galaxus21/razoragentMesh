import { v4 as uuidv4 } from "uuid";
import {
  defaultCurrency,
  defaultIntentValiditySeconds,
  mandateAmendPrefix,
  mandateCartPrefix,
  mandateExecPrefix,
  mandateIntentPrefix,
  millisPerSecond,
  signatureFieldKeys,
  uncategorizedCartItemCategory
} from "./sdkConstants.js";
import { AgentKeyManager } from "./agentKeyManager.js";
import { canonicalizeJson, computeSha256Digest } from "./jcsCanonicalizer.js";
import {
  ArithmeticDriftException,
  MandateVerificationError,
  type AmendmentMandate,
  type CartItem,
  type CartMandate,
  type ExecutionMandate,
  type IntentMandate,
  type TaxBreakdown
} from "./types.js";

export interface CreateIntentMandateParams {
  readonly mandateId?: string;
  readonly delegatedAgentDid: string;
  readonly maxBudgetPaise: number;
  readonly upiCircleDelegationToken: string;
  readonly singleTransactionLimitPaise: number;
  readonly authorizedCategories?: readonly string[];
  readonly validUntilTimestamp?: number;
  readonly nonce?: string;
  readonly timestamp?: number;
}

export interface CreateCartMandateParams {
  readonly cartId?: string;
  readonly merchantGstin: string;
  readonly merchantStateCode: string;
  readonly buyerDeliveryPincode: string;
  readonly buyerDeliveryStateCode: string;
  readonly items: readonly CartItem[];
  readonly taxableSubtotalPaise: number;
  readonly taxBreakdown: TaxBreakdown;
  readonly shippingPaise?: number;
  readonly discountPaise?: number;
  readonly totalPaise: number;
  readonly inventoryLockToken: string;
  readonly inventoryLockExpiresAt: number;
  readonly nonce?: string;
  readonly timestamp?: number;
}

export interface CreateExecutionMandateParams {
  readonly executionId?: string;
  readonly intentMandate: IntentMandate;
  readonly cartMandate: CartMandate;
  readonly settlementAmountPaise: number;
  readonly upiCircleToken: string;
  readonly nonce?: string;
  readonly timestamp?: number;
}

export interface CreateAmendmentMandateParams {
  readonly amendmentId?: string;
  readonly previousCartMandate: CartMandate;
  readonly newCartMandate: CartMandate;
  readonly substitutedSkuMapping: Readonly<Record<string, string>>;
  readonly priceDeltaPaise: number;
  readonly amendmentReason: string;
  readonly nonce?: string;
  readonly timestamp?: number;
}

export function computeMandateHash(mandate: Record<string, unknown>): string {
  const unsignedDict: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(mandate)) {
    if (!(signatureFieldKeys as readonly string[]).includes(key)) {
      unsignedDict[key] = value;
    }
  }
  const canonicalBytes = canonicalizeJson(unsignedDict);
  return computeSha256Digest(canonicalBytes);
}

export function createSignedIntentMandate(
  params: CreateIntentMandateParams,
  userSigner: AgentKeyManager
): IntentMandate {
  if (params.maxBudgetPaise <= 0 || params.singleTransactionLimitPaise <= 0) {
    throw new ArithmeticDriftException("Budget ceiling and transaction limit must be positive integer paise");
  }
  const ts = params.timestamp ?? Math.floor(Date.now() / millisPerSecond);
  const nonce = params.nonce ?? uuidv4().replace(/-/g, "");
  const mandateId = params.mandateId ?? `${mandateIntentPrefix}${uuidv4().replace(/-/g, "").slice(0, 16)}`;
  const validUntil = params.validUntilTimestamp ?? ts + defaultIntentValiditySeconds;
  const categories = params.authorizedCategories ?? [];

  const unsignedPayload = {
    authorizedCategories: categories,
    currency: defaultCurrency,
    delegatedAgentDid: params.delegatedAgentDid,
    mandateId,
    maxBudgetPaise: params.maxBudgetPaise,
    nonce,
    singleTransactionLimitPaise: params.singleTransactionLimitPaise,
    timestamp: ts,
    upiCircleDelegationToken: params.upiCircleDelegationToken,
    userDid: userSigner.getAgentDid(),
    validUntilTimestamp: validUntil
  };

  const userSignature = userSigner.signPayload(unsignedPayload);
  return { ...unsignedPayload, userSignature };
}

export const createIntentMandate = createSignedIntentMandate;

/**
 * Fills in the category the merchant is asserting. Python's CartItemSchema defaults this field
 * and always emits it, while JSON.stringify drops an undefined key entirely -- so leaving it out
 * here would make the same cart canonicalize to different bytes on the two sides and every
 * cross-SDK signature check would fail. Normalising once, before signing, keeps the wire format
 * identical whether or not the caller classified the SKU.
 */
function _withSignedCategory(item: CartItem): CartItem {
  return { ...item, category: item.category ?? uncategorizedCartItemCategory };
}

export function createSignedCartMandate(
  params: CreateCartMandateParams,
  merchantSigner: AgentKeyManager
): CartMandate {
  if (params.items.length === 0) {
    throw new Error("Cart must contain at least one item");
  }
  const ts = params.timestamp ?? Math.floor(Date.now() / millisPerSecond);
  const nonce = params.nonce ?? uuidv4().replace(/-/g, "");
  const cartId = params.cartId ?? `${mandateCartPrefix}${uuidv4().replace(/-/g, "").slice(0, 16)}`;

  const unsignedPayload = {
    buyerDeliveryPincode: params.buyerDeliveryPincode,
    buyerDeliveryStateCode: params.buyerDeliveryStateCode,
    cartId,
    discountPaise: params.discountPaise ?? 0,
    inventoryLockExpiresAt: params.inventoryLockExpiresAt,
    inventoryLockToken: params.inventoryLockToken,
    items: params.items.map(_withSignedCategory),
    merchantDid: merchantSigner.getAgentDid(),
    merchantGstin: params.merchantGstin,
    merchantStateCode: params.merchantStateCode,
    nonce,
    shippingPaise: params.shippingPaise ?? 0,
    taxBreakdown: params.taxBreakdown,
    taxableSubtotalPaise: params.taxableSubtotalPaise,
    timestamp: ts,
    totalPaise: params.totalPaise
  };

  const merchantSignature = merchantSigner.signPayload(unsignedPayload);
  return { ...unsignedPayload, merchantSignature };
}

export const createCartMandate = createSignedCartMandate;

/** The Execution Mandate exactly as it is signed: `model_dump()` minus `agentSignature`. */
export type UnsignedExecutionPayload = Omit<ExecutionMandate, "agentSignature">;

/**
 * Builds the nine-key payload an Execution Mandate signature covers, without signing it.
 *
 * Split out of `createSignedExecutionMandate` so that a caller who cannot sign in-process --
 * an MCP server handing exact bytes to an external agent that holds its own key -- derives the
 * payload from this one definition rather than restating it. The canonical shape already
 * exists in mandateFactory.py and buyerSdkPy/mandateModels.py; a fourth hand-rolled copy would
 * sign cleanly and fail verification at settlement with no useful error.
 *
 * `buyerAgentDid` is a parameter rather than a signer lookup precisely because the agent-held
 * path has a DID but no key.
 */
export function buildUnsignedExecutionPayload(
  params: CreateExecutionMandateParams,
  buyerAgentDid: string
): UnsignedExecutionPayload {
  const ts = params.timestamp ?? Math.floor(Date.now() / millisPerSecond);
  const nonce = params.nonce ?? uuidv4().replace(/-/g, "");
  const executionId = params.executionId ?? `${mandateExecPrefix}${uuidv4().replace(/-/g, "").slice(0, 16)}`;

  return {
    buyerAgentDid,
    cartMandateHash: computeMandateHash(params.cartMandate as unknown as Record<string, unknown>),
    currency: defaultCurrency,
    executionId,
    intentMandateHash: computeMandateHash(params.intentMandate as unknown as Record<string, unknown>),
    nonce,
    settlementAmountPaise: params.settlementAmountPaise,
    timestamp: ts,
    upiCircleToken: params.upiCircleToken
  };
}

export function createSignedExecutionMandate(
  params: CreateExecutionMandateParams,
  buyerAgentSigner: AgentKeyManager
): ExecutionMandate {
  const unsignedPayload = buildUnsignedExecutionPayload(params, buyerAgentSigner.getAgentDid());
  const agentSignature = buyerAgentSigner.signPayload(unsignedPayload);
  return { ...unsignedPayload, agentSignature };
}

export const createExecutionMandate = createSignedExecutionMandate;

export function createSignedAmendmentMandate(
  params: CreateAmendmentMandateParams,
  buyerAgentSigner: AgentKeyManager,
  merchantSigner: AgentKeyManager
): AmendmentMandate {
  const ts = params.timestamp ?? Math.floor(Date.now() / millisPerSecond);
  const nonce = params.nonce ?? uuidv4().replace(/-/g, "");
  const amendmentId = params.amendmentId ?? `${mandateAmendPrefix}${uuidv4().replace(/-/g, "").slice(0, 16)}`;

  const previousCartMandateHash = computeMandateHash(params.previousCartMandate as unknown as Record<string, unknown>);
  const newCartMandateHash = computeMandateHash(params.newCartMandate as unknown as Record<string, unknown>);

  const unsignedPayload = {
    amendmentId,
    amendmentReason: params.amendmentReason,
    newCartMandateHash,
    nonce,
    previousCartMandateHash,
    priceDeltaPaise: params.priceDeltaPaise,
    substitutedSkuMapping: params.substitutedSkuMapping,
    timestamp: ts
  };

  const canonicalBytes = canonicalizeJson(unsignedPayload);
  const agentSignature = buyerAgentSigner.signCanonicalBytes(canonicalBytes);
  const merchantSignature = merchantSigner.signCanonicalBytes(canonicalBytes);

  return { ...unsignedPayload, agentSignature, merchantSignature };
}

export const createAmendmentMandate = createSignedAmendmentMandate;

// Returns true when the chain holds. What happens when it does not is the caller's choice, and
// that choice used to be unavailable: this returned `boolean` but only ever returned `true` or
// threw, so `if (!verifyMandateChain(...))` typechecked and could never run its else branch. The
// parameter mirrors the Python SDK's `verifyMandateHashChain(..., raiseOnMismatch=True)`, and
// defaults to throwing so existing callers are unaffected.
export function verifyMandateChain(
  intentMandate: IntentMandate,
  cartMandate: CartMandate,
  executionMandate: ExecutionMandate,
  raiseOnMismatch: boolean = true
): boolean {
  try {
    _verifyIntentSignature(intentMandate, executionMandate);
    _verifyCartSignature(cartMandate, executionMandate);
    _verifyChainLinkage(intentMandate, cartMandate, executionMandate);
    return true;
  } catch (error) {
    // Only a failed verification becomes `false`. Anything else -- a malformed mandate that makes
    // canonicalization itself throw -- is a different problem and must not be reported as a
    // cleanly rejected chain.
    if (raiseOnMismatch || !(error instanceof MandateVerificationError)) {
      throw error;
    }
    return false;
  }
}

function _verifyIntentSignature(intentMandate: IntentMandate, executionMandate: ExecutionMandate): void {
  const computedIntentHash = computeMandateHash(intentMandate as unknown as Record<string, unknown>);
  if (computedIntentHash !== executionMandate.intentMandateHash) {
    throw new MandateVerificationError(
      `Intent mandate hash mismatch: expected ${executionMandate.intentMandateHash} (recorded in the execution mandate), got ${computedIntentHash} (recomputed now)`
    );
  }
}

function _verifyCartSignature(cartMandate: CartMandate, executionMandate: ExecutionMandate): void {
  const computedCartHash = computeMandateHash(cartMandate as unknown as Record<string, unknown>);
  if (computedCartHash !== executionMandate.cartMandateHash) {
    throw new MandateVerificationError(
      `Cart mandate hash mismatch: expected ${executionMandate.cartMandateHash} (recorded in the execution mandate), got ${computedCartHash} (recomputed now)`
    );
  }
}

function _verifyChainLinkage(
  intentMandate: IntentMandate,
  cartMandate: CartMandate,
  executionMandate: ExecutionMandate
): void {
  if (executionMandate.settlementAmountPaise !== cartMandate.totalPaise) {
    throw new MandateVerificationError(
      `Settlement amount ${executionMandate.settlementAmountPaise} does not match cart total ${cartMandate.totalPaise}`
    );
  }

  if (cartMandate.totalPaise > intentMandate.maxBudgetPaise) {
    throw new MandateVerificationError(
      `Cart total ${cartMandate.totalPaise} exceeds intent max budget ${intentMandate.maxBudgetPaise}`
    );
  }

  if (cartMandate.totalPaise > intentMandate.singleTransactionLimitPaise) {
    throw new MandateVerificationError(
      `Cart total ${cartMandate.totalPaise} exceeds single transaction limit ${intentMandate.singleTransactionLimitPaise}`
    );
  }

  if (executionMandate.timestamp > intentMandate.validUntilTimestamp) {
    throw new MandateVerificationError(
      `Intent mandate expired at ${intentMandate.validUntilTimestamp} (current: ${executionMandate.timestamp})`
    );
  }
}
