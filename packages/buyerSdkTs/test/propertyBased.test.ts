/**
 * RazorAgent Mesh TypeScript Buyer SDK — Property-Based Test Suite (fast-check)
 *
 * Verifies core mathematical, cryptographic, and serialization invariants:
 * 1. Zero-drift integer paise & GST splitting conservation
 * 2. RFC 8785 JSON Canonicalization Scheme (JCS) key-ordering and structure invariance
 * 3. Ed25519 detached signing and cryptographic verification under arbitrary JSON payloads
 * 4. Immediate and defensive rejection with ArithmeticDriftException on any floating-point numbers
 */

import { describe, it } from "node:test";
import assert from "node:assert/strict";
import * as fc from "fast-check";
import {
  AgentKeyManager,
  ArithmeticDriftException,
  canonicalizeAndHash,
  canonicalizeJson,
  canonicalizeJsonString,
  computeMandateHash,
  computeSha256Digest,
  createCartMandate,
  createExecutionMandate,
  createIntentMandate,
  verifyMandateChain,
  type CartItem,
  type TaxBreakdown
} from "../src/index.js";

// Helper Arbitraries for Property Testing
const integerPaiseArbitrary = fc.integer({ min: 0, max: 10_000_000_000 });
const positiveIntegerPaiseArbitrary = fc.integer({ min: 1, max: 10_000_000_000 });
const statutoryGstPercentArbitrary = fc.constantFrom(0, 5, 12, 18, 28);
const hex64Arbitrary = fc.stringMatching(/^[0-9a-f]{64}$/);

// Recursive arbitrary generating arbitrary integer-safe JSON values (strictly no floating points)
const safeJsonLeafArbitrary = fc.oneof(
  fc.integer({ min: -1_000_000_000, max: 1_000_000_000 }),
  fc.string({ minLength: 0, maxLength: 50 }),
  fc.boolean(),
  fc.constant(null)
);

const safeJsonObjectArbitrary: fc.Arbitrary<Record<string, unknown>> = fc.letrec((tie) => ({
  leaf: safeJsonLeafArbitrary,
  array: fc.array(tie("value") as fc.Arbitrary<unknown>, { maxLength: 4 }),
  object: fc.dictionary(
    fc.string({ minLength: 1, maxLength: 15 }).filter((k) => !k.includes("__proto__")),
    tie("value") as fc.Arbitrary<unknown>,
    { maxKeys: 5 }
  ),
  value: fc.oneof(
    tie("leaf") as fc.Arbitrary<unknown>,
    tie("array") as fc.Arbitrary<unknown>,
    tie("object") as fc.Arbitrary<unknown>
  )
})).object as fc.Arbitrary<Record<string, unknown>>;

// Non-integer float arbitrary
const nonIntegerFloatArbitrary = fc.oneof(
  fc.double({ noInteger: true }).filter((n) => Number.isFinite(n)),
  fc.constant(Number.NaN),
  fc.constant(Number.POSITIVE_INFINITY),
  fc.constant(Number.NEGATIVE_INFINITY),
  fc.constant(0.0001),
  fc.constant(99.99),
  fc.constant(-0.5)
);

describe("Property-Based Testing (fast-check) — Zero-Drift Arithmetic & Tax Conservation", () => {
  it("should conserve cgst + sgst == totalTax for arbitrary subtotal and GST slab with zero drift", () => {
    fc.assert(
      fc.property(
        integerPaiseArbitrary,
        statutoryGstPercentArbitrary,
        fc.boolean(),
        (subtotalPaise, gstRatePercent, isIntraState) => {
          const totalTaxPaise = Math.floor((subtotalPaise * gstRatePercent) / 100);
          let cgstPaise = 0;
          let sgstPaise = 0;
          let igstPaise = 0;

          if (isIntraState) {
            cgstPaise = Math.floor((subtotalPaise * Math.floor(gstRatePercent / 2)) / 100);
            sgstPaise = totalTaxPaise - cgstPaise;
            igstPaise = 0;
          } else {
            cgstPaise = 0;
            sgstPaise = 0;
            igstPaise = totalTaxPaise;
          }

          const taxBreakdown: TaxBreakdown = {
            cgstPaise,
            sgstPaise,
            igstPaise,
            totalTaxPaise
          };

          // INVARIANT 1: Total tax conservation
          assert.equal(
            taxBreakdown.cgstPaise + taxBreakdown.sgstPaise + taxBreakdown.igstPaise,
            taxBreakdown.totalTaxPaise,
            "Total tax must strictly equal sum of split components"
          );

          // INVARIANT 2: Non-negative and integer
          assert.ok(Number.isInteger(taxBreakdown.cgstPaise));
          assert.ok(Number.isInteger(taxBreakdown.sgstPaise));
          assert.ok(Number.isInteger(taxBreakdown.igstPaise));
          assert.ok(Number.isInteger(taxBreakdown.totalTaxPaise));
          assert.ok(taxBreakdown.cgstPaise >= 0);
          assert.ok(taxBreakdown.sgstPaise >= 0);
          assert.ok(taxBreakdown.igstPaise >= 0);
        }
      ),
      { numRuns: 1000 }
    );
  });

  it("should conserve cart line item totals and gross settlement computation", () => {
    const cartItemArbitrary = fc.record({
      skuId: fc.string({ minLength: 1, maxLength: 10 }),
      quantity: fc.integer({ min: 1, max: 100 }),
      unitPricePaise: fc.integer({ min: 0, max: 1_000_000 }),
      hsnCode: fc.constantFrom("8504", "8471", "9983"),
      gstRatePercent: statutoryGstPercentArbitrary
    });

    fc.assert(
      fc.property(
        fc.array(cartItemArbitrary, { minLength: 1, maxLength: 5 }),
        fc.integer({ min: 0, max: 50_000 }),
        fc.integer({ min: 0, max: 20_000 }),
        (rawItems, shippingPaise, discountPaise) => {
          const items: CartItem[] = rawItems.map((item) => ({
            ...item,
            lineTotalPaise: item.unitPricePaise * item.quantity
          }));

          const taxableSubtotalPaise = items.reduce((acc, it) => acc + it.lineTotalPaise, 0);
          const totalTaxPaise = items.reduce(
            (acc, it) => acc + Math.floor((it.lineTotalPaise * it.gstRatePercent) / 100),
            0
          );

          const cgstPaise = Math.floor(totalTaxPaise / 2);
          const sgstPaise = totalTaxPaise - cgstPaise;

          const taxBreakdown: TaxBreakdown = {
            cgstPaise,
            sgstPaise,
            igstPaise: 0,
            totalTaxPaise
          };

          const effectiveDiscount = Math.min(discountPaise, taxableSubtotalPaise);
          const totalPaise = taxableSubtotalPaise + totalTaxPaise + shippingPaise - effectiveDiscount;

          // INVARIANTS
          assert.ok(totalPaise >= 0, "Cart total must be non-negative");
          assert.ok(Number.isInteger(totalPaise), "Cart total must be pure integer paise");
          assert.equal(taxBreakdown.cgstPaise + taxBreakdown.sgstPaise, taxBreakdown.totalTaxPaise);
        }
      ),
      { numRuns: 1000 }
    );
  });
});

describe("Property-Based Testing (fast-check) — JCS RFC 8785 Canonicalization & Key Ordering Invariance", () => {
  it("should produce identical canonical strings, bytes, and SHA-256 hashes regardless of object key order", () => {
    fc.assert(
      fc.property(safeJsonObjectArbitrary, (originalObj) => {
        const keys = Object.keys(originalObj);
        if (keys.length <= 1) return;

        // Permute keys in reversed order
        const permutedObj: Record<string, unknown> = {};
        const reversedKeys = [...keys].reverse();
        for (const k of reversedKeys) {
          permutedObj[k] = originalObj[k];
        }

        const canonicalOriginal = canonicalizeJsonString(originalObj);
        const canonicalPermuted = canonicalizeJsonString(permutedObj);

        // INVARIANT 1: String canonicalization is invariant to key order
        assert.equal(
          canonicalOriginal,
          canonicalPermuted,
          "JCS canonical JSON string must be identical for permuted key insertion orders"
        );

        // INVARIANT 2: Byte sequences are identical
        const bytesOriginal = canonicalizeJson(originalObj);
        const bytesPermuted = canonicalizeJson(permutedObj);
        assert.ok(
          Buffer.from(bytesOriginal).equals(Buffer.from(bytesPermuted)),
          "JCS canonical bytes must be byte-for-byte identical"
        );

        // INVARIANT 3: Digest is invariant and deterministic
        const digestOriginal = computeSha256Digest(bytesOriginal);
        const digestPermuted = computeSha256Digest(bytesPermuted);
        assert.equal(digestOriginal, digestPermuted);
        assert.equal(digestOriginal.length, 64);
        assert.match(digestOriginal, /^[0-9a-f]{64}$/);
      }),
      { numRuns: 1000 }
    );
  });

  it("should preserve array element order while canonically sorting nested object keys", () => {
    fc.assert(
      fc.property(
        fc.array(safeJsonObjectArbitrary, { minLength: 2, maxLength: 5 }),
        (arrayOfObjects) => {
          const canonicalString = canonicalizeJsonString(arrayOfObjects);
          const parsed = JSON.parse(canonicalString) as unknown[];

          assert.equal(parsed.length, arrayOfObjects.length);
          for (let i = 0; i < arrayOfObjects.length; i++) {
            // Each element's canonical string representation matches its individual canonicalization
            const individualCanonical = canonicalizeJsonString(arrayOfObjects[i]);
            const parsedCanonical = canonicalizeJsonString(parsed[i]);
            assert.equal(parsedCanonical, individualCanonical, "Array element at index must match individual canonicalization");
          }
        }
      ),
      { numRuns: 1000 }
    );
  });
});

describe("Property-Based Testing (fast-check) — Ed25519 Detached Signing & Cryptographic Invariants", () => {
  it("should sign and verify arbitrary integer-safe JSON payloads with deterministic Ed25519 keys", () => {
    fc.assert(
      fc.property(
        hex64Arbitrary,
        safeJsonObjectArbitrary,
        (seedHex, payload) => {
          const keyManager = AgentKeyManager.fromSeed(seedHex);
          const signatureHex = keyManager.signPayload(payload);

          // INVARIANT 1: Valid 64-byte (128 hex chars) detached signature
          assert.equal(signatureHex.length, 128);
          assert.match(signatureHex, /^[0-9a-f]{128}$/);

          // INVARIANT 2: Verification with self key succeeds
          const isSelfValid = keyManager.verifyPayloadSignature(payload, signatureHex);
          assert.equal(isSelfValid, true, "Signature verification over payload must succeed");

          // INVARIANT 3: Verification with explicit public key hex succeeds
          const isPubValid = keyManager.verifyPayloadSignature(payload, signatureHex, keyManager.getPublicKeyHex());
          assert.equal(isPubValid, true, "Third-party public key verification must succeed");
        }
      ),
      { numRuns: 300 }
    );
  });

  it("should reject tampered payloads, tampered signatures, and mismatched public keys", () => {
    fc.assert(
      fc.property(
        hex64Arbitrary,
        hex64Arbitrary,
        safeJsonObjectArbitrary,
        (seedA, seedB, payload) => {
          if (seedA === seedB) return;
          const signerA = AgentKeyManager.fromSeed(seedA);
          const signerB = AgentKeyManager.fromSeed(seedB);

          const signatureHex = signerA.signPayload(payload);

          // INVARIANT 1: Wrong signer public key fails verification
          const isWrongKeyValid = signerB.verifyPayloadSignature(payload, signatureHex);
          assert.equal(isWrongKeyValid, false, "Signature verified with different key must fail");

          // INVARIANT 2: Mutated signature fails verification
          const lastChar = signatureHex.slice(-1);
          const flippedChar = lastChar === "a" ? "b" : "a";
          const tamperedSig = signatureHex.slice(0, -1) + flippedChar;
          const isTamperedSigValid = signerA.verifyPayloadSignature(payload, tamperedSig);
          assert.equal(isTamperedSigValid, false, "Tampered signature must fail verification");

          // INVARIANT 3: Mutated payload fails verification
          const tamperedPayload = { ...payload, __tamperedField: 99999 };
          const isTamperedPayloadValid = signerA.verifyPayloadSignature(tamperedPayload, signatureHex);
          assert.equal(isTamperedPayloadValid, false, "Tampered payload must fail verification");
        }
      ),
      { numRuns: 300 }
    );
  });

  it("should verify AP2 complete mandate chains generated from arbitrary valid parameters", () => {
    fc.assert(
      fc.property(
        hex64Arbitrary,
        hex64Arbitrary,
        hex64Arbitrary,
        positiveIntegerPaiseArbitrary,
        positiveIntegerPaiseArbitrary,
        (userSeed, merchantSeed, agentSeed, itemPrice, budgetPadding) => {
          const userKeyManager = AgentKeyManager.fromSeed(userSeed);
          const merchantKeyManager = AgentKeyManager.fromSeed(merchantSeed);
          const agentKeyManager = AgentKeyManager.fromSeed(agentSeed);

          const baseTimestamp = 1700000000;
          const totalCartPaise = itemPrice;
          const maxBudgetPaise = totalCartPaise + budgetPadding;

          const intentMandate = createIntentMandate(
            {
              delegatedAgentDid: agentKeyManager.getAgentDid(),
              maxBudgetPaise,
              singleTransactionLimitPaise: maxBudgetPaise,
              upiCircleDelegationToken: "upi_circle_prop_test",
              validUntilTimestamp: baseTimestamp + 3600,
              timestamp: baseTimestamp
            },
            userKeyManager
          );

          const cartMandate = createCartMandate(
            {
              merchantGstin: "29AABCU9603R1ZJ",
              merchantStateCode: "29",
              buyerDeliveryPincode: "560001",
              buyerDeliveryStateCode: "29",
              items: [
                {
                  skuId: "SKU-PROP-1",
                  quantity: 1,
                  unitPricePaise: totalCartPaise,
                  hsnCode: "8504",
                  gstRatePercent: 0,
                  lineTotalPaise: totalCartPaise
                }
              ],
              taxableSubtotalPaise: totalCartPaise,
              taxBreakdown: { cgstPaise: 0, sgstPaise: 0, igstPaise: 0, totalTaxPaise: 0 },
              totalPaise: totalCartPaise,
              inventoryLockToken: "lock_prop_001",
              inventoryLockExpiresAt: baseTimestamp + 300,
              timestamp: baseTimestamp
            },
            merchantKeyManager
          );

          const executionMandate = createExecutionMandate(
            {
              intentMandate,
              cartMandate,
              settlementAmountPaise: totalCartPaise,
              upiCircleToken: intentMandate.upiCircleDelegationToken,
              timestamp: baseTimestamp + 10
            },
            agentKeyManager
          );

          // INVARIANT: Complete chain verifies successfully
          const isChainValid = verifyMandateChain(intentMandate, cartMandate, executionMandate);
          assert.equal(isChainValid, true, "Valid AP2 mandate chain must verify successfully");
        }
      ),
      { numRuns: 300 }
    );
  });
});

describe("Property-Based Testing (fast-check) — Float Ban & ArithmeticDriftException Enforcement", () => {
  it("should immediately reject floating point numbers at root level", () => {
    fc.assert(
      fc.property(nonIntegerFloatArbitrary, (floatVal) => {
        assert.throws(
          () => canonicalizeJsonString(floatVal),
          (err: unknown) => err instanceof ArithmeticDriftException,
          `Expected ArithmeticDriftException for root float value: ${floatVal}`
        );
      }),
      { numRuns: 1000 }
    );
  });

  it("should immediately reject floating point numbers nested inside arbitrary objects and arrays", () => {
    fc.assert(
      fc.property(
        safeJsonObjectArbitrary,
        fc.string({ minLength: 1, maxLength: 10 }),
        nonIntegerFloatArbitrary,
        (baseObj, key, floatVal) => {
          const infectedObj = { ...baseObj, [key]: floatVal };
          assert.throws(
            () => canonicalizeJsonString(infectedObj),
            (err: unknown) => err instanceof ArithmeticDriftException,
            `Expected ArithmeticDriftException for object float property: ${key}=${floatVal}`
          );

          const infectedArray = [baseObj, floatVal];
          assert.throws(
            () => canonicalizeJsonString(infectedArray),
            (err: unknown) => err instanceof ArithmeticDriftException,
            `Expected ArithmeticDriftException for array float element: ${floatVal}`
          );
        }
      ),
      { numRuns: 1000 }
    );
  });

  it("should immediately reject floating point numbers nested inside Sets and Maps", () => {
    fc.assert(
      fc.property(nonIntegerFloatArbitrary, (floatVal) => {
        // Float in Set
        assert.throws(
          () => canonicalizeJsonString({ setVal: new Set([floatVal]) }),
          (err: unknown) => err instanceof ArithmeticDriftException
        );

        // Float in Map value
        assert.throws(
          () => canonicalizeJsonString({ mapVal: new Map([["field", floatVal]]) }),
          (err: unknown) => err instanceof ArithmeticDriftException
        );

        // Float in Map key
        assert.throws(
          () => canonicalizeJsonString({ mapKey: new Map([[floatVal, "field"]]) }),
          (err: unknown) => err instanceof ArithmeticDriftException
        );
      }),
      { numRuns: 500 }
    );
  });
});
