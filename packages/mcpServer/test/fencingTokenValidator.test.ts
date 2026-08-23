import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  isValidFencingToken,
  validateFencingMonotonicity,
  assertValidFencingToken
} from "../src/inventory/fencingTokenValidator.js";

describe("FencingTokenValidator", () => {
  it("should validate valid positive integer fencing tokens", () => {
    assert.equal(isValidFencingToken(1), true);
    assert.equal(isValidFencingToken(1001), true);
    assert.equal(isValidFencingToken(0), false);
    assert.equal(isValidFencingToken(-1), false);
    assert.equal(isValidFencingToken(1.5), false);
    assert.equal(isValidFencingToken(NaN), false);
  });

  it("should validate monotonic increase between fencing tokens", () => {
    assert.equal(validateFencingMonotonicity(1002, 1001), true);
    assert.equal(validateFencingMonotonicity(1001, 1001), false);
    assert.equal(validateFencingMonotonicity(1000, 1001), false);
  });

  it("should assert valid fencing token and throw on invalid token or regression", () => {
    assert.doesNotThrow(() => assertValidFencingToken(1002, 1001));
    assert.throws(() => assertValidFencingToken(0));
    assert.throws(() => assertValidFencingToken(1000, 1001));
  });
});
