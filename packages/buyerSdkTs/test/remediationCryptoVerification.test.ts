import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  canonicalizeJsonString,
  canonicalizeJson
} from "../src/jcsCanonicalizer.js";
import {
  AgentKeyManager,
  formatAgentDid,
  extractPublicKeyFromDid,
  generateAgentKeyPair
} from "../src/agentKeyManager.js";
import { ArithmeticDriftException } from "../src/types.js";

describe("Remediation Adversarial Verification — Crypto & JCS", () => {
  const buyerKeyManager = AgentKeyManager.generate();

  describe("Defect 1: verifyNoFloats in Set and Map collections", () => {
    it("should catch and reject float values in direct Set elements", () => {
      assert.throws(() => canonicalizeJsonString({ tags: new Set([10.5]) }), (err: unknown) => err instanceof ArithmeticDriftException);
      assert.throws(() => canonicalizeJsonString({ tags: new Set([0.00001]) }), (err: unknown) => err instanceof ArithmeticDriftException);
      assert.throws(() => canonicalizeJsonString({ tags: new Set([-5.25]) }), (err: unknown) => err instanceof ArithmeticDriftException);
    });

    it("should catch and reject special IEEE-754 numbers in Sets", () => {
      assert.throws(() => canonicalizeJsonString({ tags: new Set([NaN]) }), (err: unknown) => err instanceof ArithmeticDriftException);
      assert.throws(() => canonicalizeJsonString({ tags: new Set([Infinity]) }), (err: unknown) => err instanceof ArithmeticDriftException);
      assert.throws(() => canonicalizeJsonString({ tags: new Set([-Infinity]) }), (err: unknown) => err instanceof ArithmeticDriftException);
    });

    it("should catch and reject floats nested deeply within Sets", () => {
      assert.throws(() => canonicalizeJsonString({ set: new Set([{ amount: 10.5 }]) }), (err: unknown) => err instanceof ArithmeticDriftException);
      assert.throws(() => canonicalizeJsonString({ set: new Set([new Set([3.14159])]) }), (err: unknown) => err instanceof ArithmeticDriftException);
      assert.throws(() => canonicalizeJsonString({ set: new Set([[100, 200.75]]) }), (err: unknown) => err instanceof ArithmeticDriftException);
    });

    it("should catch and reject floats in Map keys and values", () => {
      assert.throws(() => canonicalizeJsonString({ map: new Map([["price", 10.5]]) }), (err: unknown) => err instanceof ArithmeticDriftException);
      assert.throws(() => canonicalizeJsonString({ map: new Map([[10.5, "price"]]) }), (err: unknown) => err instanceof ArithmeticDriftException);
      assert.throws(() => canonicalizeJsonString({ map: new Map([["nested", new Map([["inner", 0.99]])]]) }), (err: unknown) => err instanceof ArithmeticDriftException);
      assert.throws(() => canonicalizeJsonString({ map: new Map([["setVal", new Set([4.2])]]) }), (err: unknown) => err instanceof ArithmeticDriftException);
    });

    it("should deterministically canonicalize valid integer Sets and Maps", () => {
      const validPayload = {
        mySet: new Set(["charlie", "alpha", "bravo"]),
        myMap: new Map([
          ["zKey", 300],
          ["aKey", 100],
          ["mKey", 200]
        ])
      };
      const canonical = canonicalizeJsonString(validPayload);
      assert.equal(canonical, '{"myMap":{"aKey":100,"mKey":200,"zKey":300},"mySet":["alpha","bravo","charlie"]}');
    });
  });

  describe("Defect 2: verifySignature crash resilience", () => {
    it("should return false without throwing on non-hex signature strings", () => {
      const payload = { amount: 1000, recipient: "agent_alpha" };
      const rawBytes = canonicalizeJson(payload);

      assert.equal(buyerKeyManager.verifySignature(rawBytes, "z".repeat(128)), false);
      assert.equal(buyerKeyManager.verifySignature(rawBytes, "xyz123".repeat(21) + "x"), false);
      assert.equal(buyerKeyManager.verifyPayloadSignature(payload, "z".repeat(128)), false);
    });

    it("should return false on non-hex or invalid public keys", () => {
      const payload = { amount: 1000 };
      const validSig = buyerKeyManager.signPayload(payload);
      const rawBytes = canonicalizeJson(payload);

      assert.equal(buyerKeyManager.verifySignature(rawBytes, validSig, "z".repeat(64)), false);
      assert.equal(buyerKeyManager.verifySignature(rawBytes, validSig, "short_pubkey"), false);
      assert.equal(buyerKeyManager.verifyPayloadSignature(payload, validSig, "z".repeat(64)), false);
    });

    it("should return false on wrong-length signatures", () => {
      const payload = { amount: 500 };
      const rawBytes = canonicalizeJson(payload);

      assert.equal(buyerKeyManager.verifySignature(rawBytes, "a".repeat(127)), false);
      assert.equal(buyerKeyManager.verifySignature(rawBytes, "a".repeat(129)), false);
      assert.equal(buyerKeyManager.verifySignature(rawBytes, ""), false);
      assert.equal(buyerKeyManager.verifyPayloadSignature(payload, "a".repeat(64)), false);
    });

    it("should return false when canonicalBytes is invalid or non-Uint8Array", () => {
      const validSig = buyerKeyManager.signPayload({ a: 1 });
      assert.equal(buyerKeyManager.verifySignature(null as unknown as Uint8Array, validSig), false);
      assert.equal(buyerKeyManager.verifySignature(undefined as unknown as Uint8Array, validSig), false);
      assert.equal(buyerKeyManager.verifySignature("not bytes" as unknown as Uint8Array, validSig), false);
    });
  });

  describe("Defect 3: strict 64-hex seed and DID validation", () => {
    it("should throw TypeError on non-hex 64-character seeds in fromSeed", () => {
      assert.throws(() => AgentKeyManager.fromSeed("z".repeat(64)), (err: unknown) => err instanceof TypeError && (err as TypeError).message.includes("Invalid seed"));
      assert.throws(() => AgentKeyManager.fromSeed("g".repeat(64)), (err: unknown) => err instanceof TypeError && (err as TypeError).message.includes("Invalid seed"));
    });

    it("should throw TypeError on invalid seed length in fromSeed", () => {
      assert.throws(() => AgentKeyManager.fromSeed("a".repeat(63)), (err: unknown) => err instanceof TypeError);
      assert.throws(() => AgentKeyManager.fromSeed("a".repeat(65)), (err: unknown) => err instanceof TypeError);
      assert.throws(() => AgentKeyManager.fromSeed(""), (err: unknown) => err instanceof TypeError);
    });

    it("should throw TypeError in generateAgentKeyPair for non-hex seeds", () => {
      assert.throws(() => generateAgentKeyPair("z".repeat(64)), (err: unknown) => err instanceof TypeError && (err as TypeError).message.includes("Invalid seed"));
    });

    it("should throw Error in formatAgentDid and extractPublicKeyFromDid for non-hex strings", () => {
      assert.throws(() => formatAgentDid("z".repeat(64)), (err: unknown) => err instanceof Error && (err as Error).message.includes("Invalid public key hex"));
      assert.throws(() => extractPublicKeyFromDid(`did:agent:${"z".repeat(64)}`), (err: unknown) => err instanceof Error && (err as Error).message.includes("Invalid DID public key hex"));
    });

    it("should successfully initialize from valid 64-hex seed with proper casing and trimming", () => {
      const validSeedHex = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
      const km = AgentKeyManager.fromSeed(`  ${validSeedHex.toUpperCase()}  `);
      assert.ok(km.getAgentDid().startsWith("did:agent:"));
      assert.equal(km.getPublicKeyHex().length, 64);
    });
  });
});
