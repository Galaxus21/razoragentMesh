import nacl from "tweetnacl";
import {
  defaultMerchantPrivateKeyHex,
  hexEncoding,
  base64Encoding,
  utf8Encoding,
  seedByteLength
} from "../constants/protocolConstants.js";

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
