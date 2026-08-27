import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  AgentKeyManager,
  formatAgentDid,
  extractPublicKeyFromDid,
  generateAgentKeyPair
} from "../src/agentKeyManager.js";
import { canonicalizeJson } from "../src/jcsCanonicalizer.js";

describe("AgentKeyManager", () => {
  it("should generate a valid Ed25519 keypair and formatted DID", () => {
    const keyManager = AgentKeyManager.generate();
    const pubKey = keyManager.getPublicKeyHex();
    const secKey = keyManager.getSecretKeyHex();
    const did = keyManager.getAgentDid();

    assert.equal(pubKey.length, 64);
    assert.equal(secKey.length, 128);
    assert.equal(did, `did:agent:${pubKey}`);
    assert.match(did, /^did:agent:[0-9a-f]{64}$/);
  });

  it("should generate deterministic keypairs from a 32-byte seed", () => {
    const seedHex = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
    const managerA = AgentKeyManager.fromSeed(seedHex);
    const managerB = AgentKeyManager.fromSeed(seedHex);

    assert.equal(managerA.getPublicKeyHex(), managerB.getPublicKeyHex());
    assert.equal(managerA.getSecretKeyHex(), managerB.getSecretKeyHex());
    assert.equal(managerA.getAgentDid(), managerB.getAgentDid());
  });

  it("should format and extract public keys from DIDs correctly", () => {
    const pubKeyHex = "a".repeat(64);
    const did = formatAgentDid(pubKeyHex);
    assert.equal(did, `did:agent:${pubKeyHex}`);
    assert.equal(extractPublicKeyFromDid(did), pubKeyHex);

    assert.throws(() => formatAgentDid("invalid_short_hex"));
    assert.throws(() => extractPublicKeyFromDid("did:other:1234"));
    assert.throws(() => extractPublicKeyFromDid(`did:agent:${"b".repeat(60)}`));
  });

  it("should generate helper keypair struct via generateAgentKeyPair", () => {
    const seedHex = "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210";
    const keyPair = generateAgentKeyPair(seedHex);
    assert.equal(keyPair.publicKeyHex.length, 64);
    assert.equal(keyPair.secretKeyHex.length, 128);
    assert.equal(keyPair.agentDid, `did:agent:${keyPair.publicKeyHex}`);
  });

  it("should sign and verify canonical JSON payloads with detached Ed25519 signatures", () => {
    const keyManager = AgentKeyManager.generate();
    const payload = { mandateId: "M-TEST-001", amountPaise: 25000 };

    const signatureHex = keyManager.signPayload(payload);
    assert.equal(signatureHex.length, 128);
    assert.match(signatureHex, /^[0-9a-f]{128}$/);

    const isValid = keyManager.verifyPayloadSignature(payload, signatureHex);
    assert.equal(isValid, true);
  });

  it("should detect tampering when payload or signature is modified", () => {
    const keyManager = AgentKeyManager.generate();
    const payload = { mandateId: "M-TEST-002", amountPaise: 50000 };
    const signatureHex = keyManager.signPayload(payload);

    const tamperedPayload = { mandateId: "M-TEST-002", amountPaise: 99999 };
    assert.equal(keyManager.verifyPayloadSignature(tamperedPayload, signatureHex), false);

    const tamperedSignature = signatureHex[0] === "0" ? `f${signatureHex.slice(1)}` : `0${signatureHex.slice(1)}`;
    assert.equal(keyManager.verifyPayloadSignature(payload, tamperedSignature), false);
  });

  it("should verify signatures using third-party public key", () => {
    const signer = AgentKeyManager.generate();
    const verifier = AgentKeyManager.generate();

    const payload = { invoiceId: "INV-99", totalPaise: 120000 };
    const signatureHex = signer.signPayload(payload);

    assert.equal(verifier.verifyPayloadSignature(payload, signatureHex, signer.getPublicKeyHex()), true);
    assert.equal(verifier.verifyPayloadSignature(payload, signatureHex), false);
  });

  it("should sign and verify raw canonical Uint8Array bytes", () => {
    const keyManager = AgentKeyManager.generate();
    const bytes = canonicalizeJson({ test: "data", value: 42 });

    const signatureHex = keyManager.signCanonicalBytes(bytes);
    assert.equal(keyManager.verifySignature(bytes, signatureHex), true);
  });
});
