// Runtime-agnostic replacements for the Node-only primitives this SDK used to depend on.
//
// The SDK previously reached for `node:crypto`'s createHash and the global `Buffer`, which meant
// it could not be bundled for a browser at all -- webpack fails with "Can't resolve 'node:crypto'".
// That blocked the one thing a buyer agent's counterparty most wants to do: verify a mandate
// signature themselves, in their own environment, rather than trusting whoever served it.
//
// @noble/hashes gives a SYNCHRONOUS pure-JS sha256, so the swap keeps every existing signature
// synchronous. WebCrypto's digest() would have been the other option but it is async, and making
// canonicalize/hash/sign async would have rippled a breaking change through the whole public API.
// Digest output is byte-identical to the previous Node implementation; the existing suite pins it.

import { sha256 } from "@noble/hashes/sha256";

const hexCharsPerByte = 2;
const hexRadix = 16;
const hexAlphabetPattern = /^[0-9a-fA-F]*$/;

const sharedTextEncoder = new TextEncoder();

export function encodeUtf8(text: string): Uint8Array {
  return sharedTextEncoder.encode(text);
}

export function bytesToHex(bytes: Uint8Array): string {
  let hex = "";
  for (const byte of bytes) {
    hex += byte.toString(hexRadix).padStart(hexCharsPerByte, "0");
  }
  return hex.toLowerCase();
}

export function hexToBytes(hex: string): Uint8Array {
  const normalized = hex.trim().toLowerCase();
  if (normalized.length % hexCharsPerByte !== 0) {
    throw new Error(`Hex string must have an even length, got ${normalized.length}`);
  }
  if (!hexAlphabetPattern.test(normalized)) {
    throw new Error("Hex string contains non-hexadecimal characters");
  }

  const bytes = new Uint8Array(normalized.length / hexCharsPerByte);
  for (let index = 0; index < bytes.length; index += 1) {
    bytes[index] = Number.parseInt(
      normalized.slice(index * hexCharsPerByte, index * hexCharsPerByte + hexCharsPerByte),
      hexRadix
    );
  }
  return bytes;
}

export function sha256Hex(input: Uint8Array | string): string {
  const bytes = typeof input === "string" ? encodeUtf8(input) : input;
  return bytesToHex(sha256(bytes));
}
