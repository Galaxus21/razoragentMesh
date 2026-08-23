import { createHmac, timingSafeEqual } from "node:crypto";
import nacl from "tweetnacl";
import {
  defaultMerchantSecretKey,
  defaultMerchantPrivateKeyHex
} from "./mcpConstants.js";

export interface QuoteSignParams {
  readonly skuId: string;
  readonly quantity: number;
  readonly offeredUnitPricePaise: number;
  readonly totalTaxPaise: number;
  readonly quoteExpiryTimestamp: number;
  readonly buyerAgentId: string;
}

export interface LockSignParams {
  readonly lockToken: string;
  readonly fencingToken: number;
  readonly skuId: string;
  readonly quantityLocked: number;
  readonly expiresAtUnixMs: number;
}

export interface KeyPairResult {
  readonly publicKeyHex: string;
  readonly secretKeyHex: string;
  readonly publicKeyBase64: string;
}

export const hmacAlgorithm = "sha256";
export const hexEncoding = "hex";
export const base64Encoding = "base64";
export const utf8Encoding = "utf-8";
export const seedByteLength = 32;

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

export function buildLockPayload(params: LockSignParams): string {
  return `${params.lockToken}:${params.fencingToken}:${params.skuId}:${params.quantityLocked}:${params.expiresAtUnixMs}`;
}

export function getKeyPairFromSeed(seedHex: string): nacl.SignKeyPair {
  const seedBuffer = Buffer.from(seedHex, hexEncoding);
  const normalizedSeed = new Uint8Array(seedByteLength);
  const copyLength = Math.min(seedBuffer.length, seedByteLength);

  for (let index = 0; index < copyLength; index += 1) {
    normalizedSeed[index] = seedBuffer[index];
  }

  return nacl.sign.keyPair.fromSeed(normalizedSeed);
}

export function signLockPayload(
  params: LockSignParams,
  privateKeyHex: string = defaultMerchantPrivateKeyHex
): string {
  const payloadString = buildLockPayload(params);
  const messageBytes = Buffer.from(payloadString, utf8Encoding);
  const keyPair = getKeyPairFromSeed(privateKeyHex);
  const signatureBytes = nacl.sign.detached(
    new Uint8Array(messageBytes),
    keyPair.secretKey
  );

  return Buffer.from(signatureBytes).toString(base64Encoding);
}

export function verifyLockSignature(
  params: LockSignParams,
  signatureBase64: string,
  privateKeyHex: string = defaultMerchantPrivateKeyHex
): boolean {
  const payloadString = buildLockPayload(params);
  const messageBytes = Buffer.from(payloadString, utf8Encoding);
  const signatureBytes = Buffer.from(signatureBase64, base64Encoding);
  const keyPair = getKeyPairFromSeed(privateKeyHex);

  return nacl.sign.detached.verify(
    new Uint8Array(messageBytes),
    new Uint8Array(signatureBytes),
    keyPair.publicKey
  );
}

export function generateEd25519KeyPair(seedHex?: string): KeyPairResult {
  const effectiveSeed = seedHex ?? Buffer.from(nacl.randomBytes(seedByteLength)).toString(hexEncoding);
  const keyPair = getKeyPairFromSeed(effectiveSeed);

  return {
    publicKeyHex: Buffer.from(keyPair.publicKey).toString(hexEncoding),
    secretKeyHex: Buffer.from(keyPair.secretKey).toString(hexEncoding),
    publicKeyBase64: Buffer.from(keyPair.publicKey).toString(base64Encoding)
  };
}
