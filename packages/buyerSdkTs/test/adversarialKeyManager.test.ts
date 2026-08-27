import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  AgentKeyManager,
  formatAgentDid,
  extractPublicKeyFromDid,
  generateAgentKeyPair
} from "../src/agentKeyManager.js";
import { canonicalizeJson } from "../src/jcsCanonicalizer.js";

const validSeedHex = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
const validPubKeyHex = "a".repeat(64);

describe("AgentKeyManager Adversarial Stress Suite", () => {
  it("should enforce strict seed and key hex validation", () => {
    // Short seeds
    assert.throws(() => AgentKeyManager.fromSeed("0123456789abcdef"));
    assert.throws(() => AgentKeyManager.fromSeed("a".repeat(63)));
    // Long seeds
    assert.throws(() => AgentKeyManager.fromSeed("a".repeat(65)));
    assert.throws(() => AgentKeyManager.fromSeed("a".repeat(127)));
    assert.throws(() => AgentKeyManager.fromSeed("a".repeat(129)));
  });

  it("should handle casing and whitespace in seed/key hex gracefully", () => {
    const mixedSeedHex = `  ${validSeedHex.toUpperCase()}  `;
    const manager = AgentKeyManager.fromSeed(mixedSeedHex);
    assert.equal(manager.getAgentDid().startsWith("did:agent:"), true);
  });

  it("should enforce strict DID format validation", () => {
    const validDid = `did:agent:${validPubKeyHex}`;
    assert.equal(extractPublicKeyFromDid(validDid), validPubKeyHex);

    // Malformed DID prefixes
    assert.throws(() => extractPublicKeyFromDid("did:key:1234567890"));
    assert.throws(() => extractPublicKeyFromDid("did:mesh:1234567890"));
    assert.throws(() => extractPublicKeyFromDid("agent:did:1234567890"));
    assert.throws(() => extractPublicKeyFromDid(""));

    // Malformed DID lengths
    assert.throws(() => extractPublicKeyFromDid(`did:agent:${"a".repeat(63)}`));
    assert.throws(() => extractPublicKeyFromDid(`did:agent:${"a".repeat(65)}`));
    assert.throws(() => extractPublicKeyFromDid("did:agent:"));

    // Format agent DID validation
    assert.throws(() => formatAgentDid("a".repeat(63)));
    assert.throws(() => formatAgentDid("a".repeat(65)));
    assert.throws(() => formatAgentDid(""));
  });

  it("should reject corrupted, truncated, and padded signatures", () => {
    const keyManager = AgentKeyManager.generate();
    const payload = { amountPaise: 100000, recipient: "agent_alpha", nonce: "nonce_123" };
    const validSignature = keyManager.signPayload(payload);
    const rawBytes = canonicalizeJson(payload);

    assert.equal(keyManager.verifyPayloadSignature(payload, validSignature), true);

    // Bit flip in signature
    const corruptedChar = validSignature[0] === "0" ? "1" : "0";
    const bitFlippedSig = `${corruptedChar}${validSignature.slice(1)}`;
    assert.equal(keyManager.verifyPayloadSignature(payload, bitFlippedSig), false);

    // Truncated signatures
    assert.equal(keyManager.verifyPayloadSignature(payload, validSignature.slice(0, 127)), false);
    assert.equal(keyManager.verifyPayloadSignature(payload, validSignature.slice(0, 64)), false);
    assert.equal(keyManager.verifyPayloadSignature(payload, ""), false);

    // Overlong/padded signature
    assert.equal(keyManager.verifyPayloadSignature(payload, `${validSignature}00`), false);

    // Byte verification with length-mismatched public key
    assert.equal(keyManager.verifySignature(rawBytes, validSignature, "a".repeat(63)), false);

    // Non-hex signature string should safely return false without throwing/crashing
    assert.equal(keyManager.verifySignature(rawBytes, "z".repeat(128)), false);
    assert.equal(keyManager.verifyPayloadSignature(payload, "z".repeat(128)), false);
    assert.equal(keyManager.verifySignature(rawBytes, validSignature, "z".repeat(64)), false);
  });

  it("should reject non-hex seeds, secret keys, and DIDs with clean descriptive errors", () => {
    // Non-hex 64-char seed
    assert.throws(
      () => AgentKeyManager.fromSeed("z".repeat(64)),
      (err: unknown) => err instanceof TypeError && (err as TypeError).message.includes("Invalid seed")
    );

    // Non-hex 128-char secret key
    assert.throws(
      () => AgentKeyManager.fromSecretKey("z".repeat(128)),
      (err: unknown) => err instanceof Error && (err as Error).message.includes("Invalid secret key")
    );

    // Non-hex formatAgentDid
    assert.throws(
      () => formatAgentDid("z".repeat(64)),
      (err: unknown) => err instanceof Error && (err as Error).message.includes("Invalid public key hex")
    );

    // Non-hex extractPublicKeyFromDid
    assert.throws(
      () => extractPublicKeyFromDid(`did:agent:${"z".repeat(64)}`),
      (err: unknown) => err instanceof Error && (err as Error).message.includes("Invalid DID public key hex")
    );

    // Non-hex generateAgentKeyPair seed
    assert.throws(
      () => generateAgentKeyPair("z".repeat(64)),
      (err: unknown) => err instanceof TypeError && (err as TypeError).message.includes("Invalid seed")
    );
  });

  it("should generate deterministic keypairs from 32-byte seed across repeated calls", () => {
    const keyPair1 = generateAgentKeyPair(validSeedHex);
    const keyPair2 = generateAgentKeyPair(validSeedHex);

    assert.equal(keyPair1.publicKeyHex, keyPair2.publicKeyHex);
    assert.equal(keyPair1.secretKeyHex, keyPair2.secretKeyHex);
    assert.equal(keyPair1.agentDid, keyPair2.agentDid);
  });

  it("should initialize AgentKeyManager from 64-byte secret key hex", () => {
    const original = AgentKeyManager.generate();
    const secretKeyHex = original.getSecretKeyHex();
    const restored = AgentKeyManager.fromSecretKey(secretKeyHex);

    assert.equal(restored.getPublicKeyHex(), original.getPublicKeyHex());
    assert.equal(restored.getAgentDid(), original.getAgentDid());

    const testPayload = { message: "secret_key_restore_test" };
    const signature = restored.signPayload(testPayload);
    assert.equal(original.verifyPayloadSignature(testPayload, signature), true);
  });
});
