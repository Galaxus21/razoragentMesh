export interface AgentKeyPair {
  readonly publicKeyHex: string;
  readonly secretKeyHex: string;
  readonly agentDid: string;
}

export interface TaxBreakdown {
  readonly cgstPaise: number;
  readonly sgstPaise: number;
  readonly igstPaise: number;
  readonly totalTaxPaise: number;
}

export interface CartItem {
  readonly skuId: string;
  readonly quantity: number;
  readonly unitPricePaise: number;
  readonly hsnCode: string;
  readonly gstRatePercent: number;
  readonly lineTotalPaise: number;
  /**
   * Merchant-asserted product category, checked at settlement against the Intent Mandate's
   * `authorizedCategories`. Optional to supply; `createSignedCartMandate` fills in
   * `uncategorizedCartItemCategory` so the signed payload always carries the key.
   */
  readonly category?: string;
}

export interface IntentMandate {
  readonly mandateId: string;
  readonly userDid: string;
  readonly delegatedAgentDid: string;
  readonly maxBudgetPaise: number;
  readonly currency: "INR";
  readonly authorizedCategories: readonly string[];
  readonly validUntilTimestamp: number;
  readonly upiCircleDelegationToken: string;
  readonly singleTransactionLimitPaise: number;
  readonly nonce: string;
  readonly timestamp: number;
  readonly userSignature: string;
}

export interface CartMandate {
  readonly cartId: string;
  readonly merchantDid: string;
  readonly merchantGstin: string;
  readonly merchantStateCode: string;
  readonly buyerDeliveryPincode: string;
  readonly buyerDeliveryStateCode: string;
  readonly items: readonly CartItem[];
  readonly taxableSubtotalPaise: number;
  readonly taxBreakdown: TaxBreakdown;
  readonly shippingPaise: number;
  readonly discountPaise: number;
  readonly totalPaise: number;
  readonly inventoryLockToken: string;
  readonly inventoryLockExpiresAt: number;
  readonly nonce: string;
  readonly timestamp: number;
  readonly merchantSignature: string;
}

export interface ExecutionMandate {
  readonly executionId: string;
  readonly buyerAgentDid: string;
  readonly intentMandateHash: string;
  readonly cartMandateHash: string;
  readonly settlementAmountPaise: number;
  readonly currency: "INR";
  readonly upiCircleToken: string;
  readonly nonce: string;
  readonly timestamp: number;
  readonly agentSignature: string;
}

export interface AmendmentMandate {
  readonly amendmentId: string;
  readonly previousCartMandateHash: string;
  readonly newCartMandateHash: string;
  readonly substitutedSkuMapping: Readonly<Record<string, string>>;
  readonly priceDeltaPaise: number;
  readonly amendmentReason: string;
  readonly nonce: string;
  readonly timestamp: number;
  readonly agentSignature: string;
  readonly merchantSignature: string;
}

export interface PoWChallenge {
  readonly statusCode: number;
  readonly wwwAuthenticate: string;
  readonly challengeToken: string;
  readonly tokenCostPaise: number;
  readonly powDifficultyZeros: number;
}

export type Http402ChallengeResponse = PoWChallenge;

export interface PoWSolution {
  readonly nonce: number;
  readonly computedDigest: string;
  readonly elapsedMs: number;
}

export type PowSolveResult = PoWSolution;

export interface PowVerificationResult {
  readonly isValid: boolean;
  readonly challengeToken: string;
  readonly computedDigest: string;
  readonly errorMessage?: string;
}

export interface AppliedDiscount {
  readonly code: string;
  readonly name: string;
  readonly discountPaise: number;
  readonly type?: string;
}

export interface UpcomingPromotion {
  readonly campaignId: string;
  readonly name: string;
  readonly startsAtUnix: number;
  readonly endsAtUnix: number;
  readonly expectedUnitPricePaise: number;
  readonly expectedSavingsPaise: number;
  readonly limitedStockAllocated?: number;
}

export interface SkuQuote {
  readonly skuId: string;
  // HSN chapter and its statutory GST rate travel with the quote because a CartMandate line
  // item requires both, and re-deriving them buyer-side would let the buyer pick its own tax
  // rate. They come from the merchant's catalog, alongside the price.
  readonly hsnCode: string;
  readonly gstRatePercent: number;
  readonly baseUnitPricePaise: number;
  readonly offeredUnitPricePaise?: number;
  readonly finalUnitPricePaise: number;
  readonly availableStock?: number;
  readonly quantity: number;
  readonly taxableSubtotalPaise: number;
  readonly taxBreakdown: TaxBreakdown;
  readonly appliedDiscounts: readonly AppliedDiscount[];
  readonly totalSavingsPaise: number;
  readonly quoteExpiryTimestamp: number;
  readonly quoteHash: string;
  readonly upcomingPromotions?: readonly UpcomingPromotion[];
}

export type SkuQuoteResponse = SkuQuote;

export interface InventoryLockRequest {
  readonly skuId: string;
  readonly quantity: number;
  readonly buyerAgentDid: string;
  readonly lockTtlSeconds?: number;
  readonly quoteHash?: string;
}

export interface InventoryLockResponse {
  readonly lockToken: string;
  readonly fencingToken: number;
  readonly skuId: string;
  readonly quantityLocked: number;
  readonly expiresAtUnixMs: number;
  readonly lockSignature: string;
}

export type StockLockResponse = InventoryLockResponse;

export interface SlaVerificationResponse {
  readonly pincode: string;
  readonly zone: string;
  readonly deliverySpeed: string;
  readonly slaHours: number;
  readonly shippingFeePaise: number;
  readonly weightGrams: number;
}

export interface SplitTransfer {
  readonly id: string;
  readonly account: string;
  readonly amount: number;
  readonly currency: string;
  readonly status?: string;
}

export interface GstrInvoice {
  readonly invoiceNumber: string;
  readonly merchantGstin: string;
  readonly buyerDeliveryStateCode: string;
  readonly taxableAmountPaise: number;
  readonly totalCgstPaise: number;
  readonly totalSgstPaise: number;
  readonly totalIgstPaise: number;
  readonly grandTotalPaise: number;
  readonly cryptographicAuditHash: string;
}

export interface SettlementRequest {
  readonly intentMandate: IntentMandate;
  readonly cartMandate: CartMandate;
  readonly executionMandate: ExecutionMandate;
  readonly merchantAccount: string;
  readonly paymentId: string;
  readonly serverTime?: number;
  readonly metadata?: Readonly<Record<string, unknown>>;
}

export type ExecuteSettlementRequest = SettlementRequest;

export interface SettlementResult {
  readonly status: string;
  readonly paymentId: string;
  readonly amountPaise: number;
  readonly currency: string;
  readonly transfers: readonly SplitTransfer[];
  readonly invoice: GstrInvoice;
  readonly settledAt?: number;
}

export interface PriceDropAlert {
  readonly skuId: string;
  readonly targetPricePaise: number;
  readonly activePricePaise: number;
  readonly concessionPaise: number;
  readonly promotionId?: string;
}

export class ArithmeticDriftException extends Error {
  public constructor(message: string) {
    super(message);
    this.name = "ArithmeticDriftException";
  }
}

export class MandateVerificationError extends Error {
  public constructor(message: string) {
    super(message);
    this.name = "MandateVerificationError";
  }
}

export class PoWVerificationError extends Error {
  public constructor(message: string) {
    super(message);
    this.name = "PoWVerificationError";
  }
}

export class ClientRequestError extends Error {
  public readonly statusCode: number;

  public constructor(message: string, statusCode: number) {
    super(message);
    this.name = "ClientRequestError";
    this.statusCode = statusCode;
  }
}
