import {
  defaultLockTtlSeconds, defaultMandateEngineUrl, defaultMcpServerUrl, defaultPowDifficultyZeros,
  defaultPurchaseQuantity, defaultSlaWeightGrams, defaultX402GatewayUrl, endpointLock,
  endpointQuote, endpointSettlementExecute, endpointSla, httpMethodGet, httpMethodPost,
  mandateCartAmendedPrefix, mandateCartPrefix, mediaTypeApplicationJson
} from "./sdkConstants.js";
import { AgentKeyManager } from "./agentKeyManager.js";
import {
  createSignedAmendmentMandate, createSignedExecutionMandate, verifyMandateChain
} from "./agentMandateBuilder.js";
import { generatePowHeaders, solvePowChallenge } from "./powSolver.js";
import {
  ClientRequestError, type AmendmentMandate, type CartMandate, type Http402ChallengeResponse,
  type IntentMandate, type InventoryLockResponse, type PriceDropAlert, type SettlementRequest,
  type SettlementResult, type SkuQuote, type SlaVerificationResponse
} from "./types.js";

export interface RazorAgentClientConfig {
  readonly mandateEngineUrl?: string;
  readonly mcpServerUrl?: string;
  readonly x402GatewayUrl?: string;
  readonly buyerKeyManager?: AgentKeyManager;
  readonly customFetch?: typeof fetch;
  readonly defaultLockTtlSeconds?: number;
}

export interface QuoteOptions {
  readonly deliveryPincode?: string;
  readonly promoCode?: string;
  readonly merchantDid?: string;
}

export interface LockOptions {
  readonly lockTtlSeconds?: number;
  readonly quoteHash?: string;
  readonly escrowToken?: string;
  readonly maxRetries?: number;
}

export interface AutonomousPurchaseParams {
  readonly skuId: string;
  readonly quantity: number;
  readonly intentMandate: IntentMandate;
  readonly cartMandate: CartMandate;
  readonly merchantAccount: string;
  readonly paymentId: string;
  readonly serverTime?: number;
}

interface AlertComputationResult {
  readonly priceDeltaPaise: number;
  readonly newTotalPaise: number;
  readonly amendedCartId: string;
}

export class RazorAgentClient {
  private readonly _mandateEngineUrl: string;
  private readonly _mcpServerUrl: string;
  private readonly _x402GatewayUrl: string;
  private readonly _buyerKeyManager: AgentKeyManager;
  private readonly _fetch: typeof fetch;
  private readonly _defaultLockTtlSeconds: number;

  public constructor(config: RazorAgentClientConfig = {}) {
    this._mandateEngineUrl = (config.mandateEngineUrl ?? defaultMandateEngineUrl).replace(/\/$/, "");
    this._mcpServerUrl = (config.mcpServerUrl ?? defaultMcpServerUrl).replace(/\/$/, "");
    this._x402GatewayUrl = (config.x402GatewayUrl ?? defaultX402GatewayUrl).replace(/\/$/, "");
    this._buyerKeyManager = config.buyerKeyManager ?? AgentKeyManager.generate();
    this._fetch = config.customFetch ?? globalThis.fetch;
    this._defaultLockTtlSeconds = config.defaultLockTtlSeconds ?? defaultLockTtlSeconds;
  }

  public getBuyerKeyManager(): AgentKeyManager {
    return this._buyerKeyManager;
  }

  public getAgentDid(): string {
    return this._buyerKeyManager.getAgentDid();
  }

  public async getLiveSkuQuote(
    skuId: string,
    quantity: number = defaultPurchaseQuantity,
    options: QuoteOptions = {}
  ): Promise<SkuQuote> {
    const query = new URLSearchParams({
      skuId,
      quantity: quantity.toString(),
      buyerAgentDid: this.getAgentDid()
    });
    if (options.deliveryPincode) query.set("deliveryPincode", options.deliveryPincode);
    if (options.promoCode) query.set("promoCode", options.promoCode);

    const url = `${this._mcpServerUrl}${endpointQuote}?${query.toString()}`;
    const response = await this._fetch(url, {
      method: httpMethodGet,
      headers: { Accept: mediaTypeApplicationJson }
    });
    if (!response.ok) {
      throw new ClientRequestError(`Failed to fetch quote: HTTP ${response.status}`, response.status);
    }
    return (await response.json()) as SkuQuote;
  }

  public async reserveInventoryLock(
    skuId: string,
    quantity: number = defaultPurchaseQuantity,
    options: LockOptions = {}
  ): Promise<InventoryLockResponse> {
    const lockTtl = options.lockTtlSeconds ?? this._defaultLockTtlSeconds;
    const bodyPayload = {
      skuId,
      quantity,
      buyerAgentDid: this.getAgentDid(),
      lockTtlSeconds: lockTtl,
      quoteHash: options.quoteHash
    };
    const url = `${this._mcpServerUrl}${endpointLock}`;
    const initialResponse = await this._fetch(url, {
      method: httpMethodPost,
      headers: { "Content-Type": mediaTypeApplicationJson, Accept: mediaTypeApplicationJson },
      body: JSON.stringify(bodyPayload)
    });

    if (initialResponse.status === 402) {
      return this._handlePowChallengeAndRetry(url, bodyPayload, initialResponse, options.escrowToken);
    }
    if (!initialResponse.ok) {
      throw new ClientRequestError(`Failed to reserve lock: HTTP ${initialResponse.status}`, initialResponse.status);
    }
    return (await initialResponse.json()) as InventoryLockResponse;
  }

  private async _handlePowChallengeAndRetry(
    url: string,
    bodyPayload: Record<string, unknown>,
    response402: Response,
    escrowToken?: string
  ): Promise<InventoryLockResponse> {
    const challengeData = (await response402.json()) as Http402ChallengeResponse;
    const difficulty = challengeData.powDifficultyZeros ?? defaultPowDifficultyZeros;
    const powResult = solvePowChallenge(challengeData.challengeToken, difficulty);
    const powHeaders = generatePowHeaders(challengeData.challengeToken, powResult.nonce, this.getAgentDid(), escrowToken);

    const retryResponse = await this._fetch(url, {
      method: httpMethodPost,
      headers: { "Content-Type": mediaTypeApplicationJson, Accept: mediaTypeApplicationJson, ...powHeaders },
      body: JSON.stringify(bodyPayload)
    });

    if (!retryResponse.ok) {
      throw new ClientRequestError(`PoW retry lock failed: HTTP ${retryResponse.status}`, retryResponse.status);
    }
    return (await retryResponse.json()) as InventoryLockResponse;
  }

  public async verifyShippingSla(
    pincode: string,
    weightGrams: number = defaultSlaWeightGrams
  ): Promise<SlaVerificationResponse> {
    const query = new URLSearchParams({ pincode, weightGrams: weightGrams.toString() });
    const url = `${this._mcpServerUrl}${endpointSla}?${query.toString()}`;
    const response = await this._fetch(url, {
      method: httpMethodGet,
      headers: { Accept: mediaTypeApplicationJson }
    });
    if (!response.ok) {
      throw new ClientRequestError(`Failed to verify SLA: HTTP ${response.status}`, response.status);
    }
    return (await response.json()) as SlaVerificationResponse;
  }

  public async executeSettlement(request: SettlementRequest): Promise<SettlementResult> {
    verifyMandateChain(request.intentMandate, request.cartMandate, request.executionMandate);
    const url = `${this._mandateEngineUrl}${endpointSettlementExecute}`;
    const response = await this._fetch(url, {
      method: httpMethodPost,
      headers: { "Content-Type": mediaTypeApplicationJson, Accept: mediaTypeApplicationJson },
      body: JSON.stringify(request)
    });
    if (!response.ok) {
      const errorText = await response.text();
      throw new ClientRequestError(`Settlement failed: [HTTP ${response.status}] ${errorText}`, response.status);
    }
    return (await response.json()) as SettlementResult;
  }

  public async executeAutonomousPurchase(params: AutonomousPurchaseParams): Promise<SettlementResult> {
    const executionMandate = createSignedExecutionMandate(
      {
        intentMandate: params.intentMandate,
        cartMandate: params.cartMandate,
        settlementAmountPaise: params.cartMandate.totalPaise,
        upiCircleToken: params.intentMandate.upiCircleDelegationToken,
        timestamp: params.serverTime
      },
      this._buyerKeyManager
    );

    return this.executeSettlement({
      intentMandate: params.intentMandate,
      cartMandate: params.cartMandate,
      executionMandate,
      merchantAccount: params.merchantAccount,
      paymentId: params.paymentId,
      serverTime: params.serverTime
    });
  }

  public handlePriceDropAlert(
    alert: PriceDropAlert,
    previousCartMandate: CartMandate,
    merchantSigner: AgentKeyManager
  ): AmendmentMandate {
    return _computeAlertAction(alert, previousCartMandate, merchantSigner, this._buyerKeyManager);
  }
}

function _validateAlertPayload(
  alert: PriceDropAlert,
  previousCartMandate: CartMandate
): AlertComputationResult {
  const priceDeltaPaise = Math.max(0, alert.concessionPaise);
  const newTotalPaise = Math.max(0, previousCartMandate.totalPaise - priceDeltaPaise);
  const cartSuffix = previousCartMandate.cartId.startsWith(mandateCartPrefix)
    ? previousCartMandate.cartId.slice(mandateCartPrefix.length)
    : previousCartMandate.cartId;
  const amendedCartId = `${mandateCartAmendedPrefix}${cartSuffix.slice(0, 16)}`;

  return { priceDeltaPaise, newTotalPaise, amendedCartId };
}

function _buildUnsignedAmendedCart(
  previousCartMandate: CartMandate,
  amendedCartId: string,
  priceDeltaPaise: number,
  newTotalPaise: number,
  merchantDid: string
): Omit<CartMandate, "merchantSignature"> {
  return {
    buyerDeliveryPincode: previousCartMandate.buyerDeliveryPincode,
    buyerDeliveryStateCode: previousCartMandate.buyerDeliveryStateCode,
    cartId: amendedCartId,
    discountPaise: previousCartMandate.discountPaise + priceDeltaPaise,
    inventoryLockExpiresAt: previousCartMandate.inventoryLockExpiresAt,
    inventoryLockToken: previousCartMandate.inventoryLockToken,
    items: previousCartMandate.items,
    merchantDid,
    merchantGstin: previousCartMandate.merchantGstin,
    merchantStateCode: previousCartMandate.merchantStateCode,
    nonce: previousCartMandate.nonce,
    shippingPaise: previousCartMandate.shippingPaise,
    taxBreakdown: previousCartMandate.taxBreakdown,
    taxableSubtotalPaise: previousCartMandate.taxableSubtotalPaise,
    timestamp: previousCartMandate.timestamp,
    totalPaise: newTotalPaise
  };
}

function _computeAlertAction(
  alert: PriceDropAlert,
  previousCartMandate: CartMandate,
  merchantSigner: AgentKeyManager,
  buyerKeyManager: AgentKeyManager
): AmendmentMandate {
  const { priceDeltaPaise, newTotalPaise, amendedCartId } = _validateAlertPayload(alert, previousCartMandate);
  const unsignedAmendedCart = _buildUnsignedAmendedCart(
    previousCartMandate,
    amendedCartId,
    priceDeltaPaise,
    newTotalPaise,
    merchantSigner.getAgentDid()
  );
  const merchantSignature = merchantSigner.signPayload(unsignedAmendedCart);
  const updatedCartMandate: CartMandate = { ...unsignedAmendedCart, merchantSignature };

  return createSignedAmendmentMandate(
    {
      previousCartMandate,
      newCartMandate: updatedCartMandate,
      substitutedSkuMapping: { [alert.skuId]: alert.skuId },
      priceDeltaPaise,
      amendmentReason: `Temporal price-drop concession: saved ${priceDeltaPaise} paise`
    },
    buyerKeyManager,
    merchantSigner
  );
}

