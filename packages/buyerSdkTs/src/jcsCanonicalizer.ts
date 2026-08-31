import { encodeUtf8, sha256Hex } from "./isomorphicCrypto.js";
import { ArithmeticDriftException } from "./types.js";

export function canonicalizeJsonString(payload: unknown): string {
  _verifyNoFloats(payload);
  const normalized = _normalizeForJcs(payload);
  return JSON.stringify(normalized);
}

export function canonicalizeJson(payload: unknown): Uint8Array {
  const jsonString = canonicalizeJsonString(payload);
  return encodeUtf8(jsonString);
}

export function computeSha256Digest(canonicalBytes: Uint8Array | string): string {
  return sha256Hex(canonicalBytes);
}

export function canonicalizeAndHash(payload: unknown): {
  readonly canonicalBytes: Uint8Array;
  readonly digest: string;
} {
  const canonicalBytes = canonicalizeJson(payload);
  const digest = computeSha256Digest(canonicalBytes);
  return { canonicalBytes, digest };
}

function _verifyNoFloats(data: unknown): void {
  if (typeof data === "number") {
    if (!Number.isInteger(data)) {
      throw new ArithmeticDriftException(
        `Floating-point value '${data}' detected: financial payloads must use integer paise`
      );
    }
    return;
  }
  if (data === null || data === undefined || typeof data !== "object") {
    return;
  }
  if (Array.isArray(data)) {
    for (const item of data) {
      _verifyNoFloats(item);
    }
    return;
  }
  if (data instanceof Set) {
    for (const item of data) {
      _verifyNoFloats(item);
    }
    return;
  }
  if (data instanceof Map) {
    for (const [key, value] of data.entries()) {
      _verifyNoFloats(key);
      _verifyNoFloats(value);
    }
    return;
  }
  for (const [key, value] of Object.entries(data as Record<string, unknown>)) {
    _verifyNoFloats(key);
    _verifyNoFloats(value);
  }
}

function _normalizeForJcs(data: unknown): unknown {
  if (data === null || typeof data !== "object") {
    return data;
  }
  if (Array.isArray(data)) {
    return data.map((item) => _normalizeForJcs(item));
  }
  if (data instanceof Set) {
    return Array.from(data)
      .map((item) => _normalizeForJcs(item))
      .sort((itemA, itemB) => {
        const strA = typeof itemA === "string" ? itemA : JSON.stringify(itemA);
        const strB = typeof itemB === "string" ? itemB : JSON.stringify(itemB);
        return strA < strB ? -1 : strA > strB ? 1 : 0;
      });
  }
  if (data instanceof Map) {
    const entries = Array.from(data.entries()).map(([key, value]) => [String(key), _normalizeForJcs(value)] as const);
    entries.sort(([keyA], [keyB]) => (keyA < keyB ? -1 : keyA > keyB ? 1 : 0));
    const sortedObj: Record<string, unknown> = {};
    for (const [key, value] of entries) {
      sortedObj[key] = value;
    }
    return sortedObj;
  }
  const entries = Object.entries(data as Record<string, unknown>);
  entries.sort(([keyA], [keyB]) => (keyA < keyB ? -1 : keyA > keyB ? 1 : 0));
  const sortedObj: Record<string, unknown> = {};
  for (const [key, value] of entries) {
    sortedObj[key] = _normalizeForJcs(value);
  }
  return sortedObj;
}
