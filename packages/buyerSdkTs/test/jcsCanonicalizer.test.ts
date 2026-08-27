import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  canonicalizeJsonString,
  canonicalizeJson,
  computeSha256Digest,
  canonicalizeAndHash
} from "../src/jcsCanonicalizer.js";
import { ArithmeticDriftException } from "../src/types.js";

describe("jcsCanonicalizer", () => {
  it("should sort object keys lexicographically in canonical string output", () => {
    const unordered = {
      zebra: 100,
      apple: 200,
      mango: {
        yellow: 1,
        green: 2
      }
    };
    const canonical = canonicalizeJsonString(unordered);
    assert.equal(canonical, '{"apple":200,"mango":{"green":2,"yellow":1},"zebra":100}');
  });

  it("should preserve array ordering while sorting object keys inside arrays", () => {
    const payload = [
      { z: 1, a: 2 },
      { y: 3, b: 4 }
    ];
    const canonical = canonicalizeJsonString(payload);
    assert.equal(canonical, '[{"a":2,"z":1},{"b":4,"y":3}]');
  });

  it("should reject floating point numbers anywhere in payload", () => {
    assert.throws(
      () => canonicalizeJsonString({ price: 42.5 }),
      (err: unknown) => err instanceof ArithmeticDriftException
    );

    assert.throws(
      () => canonicalizeJsonString({ items: [{ subtotal: 10.001 }] }),
      (err: unknown) => err instanceof ArithmeticDriftException
    );

    assert.throws(
      () => canonicalizeJsonString({ invalid: Number.NaN }),
      (err: unknown) => err instanceof ArithmeticDriftException
    );

    assert.throws(
      () => canonicalizeJsonString({ invalid: Number.POSITIVE_INFINITY }),
      (err: unknown) => err instanceof ArithmeticDriftException
    );
  });

  it("should accept valid integer paise numbers", () => {
    const payload = { amountPaise: 420000, zeroPaise: 0, taxPaise: 75600 };
    const canonical = canonicalizeJsonString(payload);
    assert.equal(canonical, '{"amountPaise":420000,"taxPaise":75600,"zeroPaise":0}');
  });

  it("should compute deterministic SHA-256 digest from canonical bytes", () => {
    const payload = { mandateId: "M-001", amountPaise: 50000 };
    const { canonicalBytes, digest } = canonicalizeAndHash(payload);
    const expectedHash = computeSha256Digest(canonicalBytes);

    assert.equal(digest, expectedHash);
    assert.equal(digest.length, 64);
    assert.match(digest, /^[0-9a-f]{64}$/);
  });

  it("should reject floating point numbers in Sets and Maps", () => {
    assert.throws(
      () => canonicalizeJsonString({ tags: new Set([10.5]) }),
      (err: unknown) => err instanceof ArithmeticDriftException
    );

    assert.throws(
      () => canonicalizeJsonString({ map: new Map([["key", 10.5]]) }),
      (err: unknown) => err instanceof ArithmeticDriftException
    );

    assert.throws(
      () => canonicalizeJsonString({ map: new Map([[10.5, "val"]]) }),
      (err: unknown) => err instanceof ArithmeticDriftException
    );

    assert.throws(
      () => canonicalizeJsonString({ nested: new Set([new Set([10.5])]) }),
      (err: unknown) => err instanceof ArithmeticDriftException
    );
  });

  it("should sort and serialize Sets and Maps deterministically with integer paise", () => {
    const setPayload = { tags: new Set(["beta", "alpha", "gamma"]) };
    const setCanonical = canonicalizeJsonString(setPayload);
    assert.equal(setCanonical, '{"tags":["alpha","beta","gamma"]}');

    const mapPayload = {
      rates: new Map([
        ["cgst", 900],
        ["sgst", 900],
        ["igst", 0]
      ])
    };
    const mapCanonical = canonicalizeJsonString(mapPayload);
    assert.equal(mapCanonical, '{"rates":{"cgst":900,"igst":0,"sgst":900}}');
  });
});
