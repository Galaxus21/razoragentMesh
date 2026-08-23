import { createHmac, timingSafeEqual } from "node:crypto";
import {
  defaultMerchantSecretKey,
  hmacAlgorithm,
  hexEncoding,
  utf8Encoding
} from "../constants/protocolConstants.js";

export interface QuoteSignParams {
  readonly skuId: string;
  readonly quantity: number;
  readonly offeredUnitPricePaise: number;
  readonly totalTaxPaise: number;
  readonly quoteExpiryTimestamp: number;
  readonly buyerAgentId: string;
}

export function buildQuotePayload(params: QuoteSignParams): string {
  return `${params.skuId}:${params.quantity}:${params.offeredUnitPricePaise}:${params.totalTaxPaise}:${params.quoteExpiryTimestamp}:${params.buyerAgentId}`;
}

export function computeQuoteHash(
  params: QuoteSignParams,
  secretKey: string = defaultMerchantSecretKey
): string {
  const payloadString = buildQuotePayload(params);
  return createHmac(hmacAlgorithm, secretKey)
    .update(payloadString, utf8Encoding)
    .digest(hexEncoding);
}

export function verifyQuoteHash(
  params: QuoteSignParams,
  expectedHash: string,
  secretKey: string = defaultMerchantSecretKey
): boolean {
  const actualHash = computeQuoteHash(params, secretKey);
  const actualBuffer = Buffer.from(actualHash, hexEncoding);
  const expectedBuffer = Buffer.from(expectedHash, hexEncoding);

  if (actualBuffer.length !== expectedBuffer.length) {
    return false;
  }

  return timingSafeEqual(actualBuffer, expectedBuffer);
}
