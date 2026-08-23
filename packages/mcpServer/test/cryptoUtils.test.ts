import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  computeQuoteHash,
  verifyQuoteHash,
  signLockPayload,
  verifyLockSignature,
  generateEd25519KeyPair
} from "../src/cryptoUtils.js";

describe("CryptoUtils", () => {
  const sampleQuote = {
    skuId: "SKU-CHAIR-001",
    quantity: 5,
    offeredUnitPricePaise: 420000,
    totalTaxPaise: 378000,
    quoteExpiryTimestamp: 1756000000,
    buyerAgentId: "did:agent:enterprise-procure-bot-01"
  };

  it("should generate deterministic HMAC-SHA256 quote hash", () => {
    const hash1 = computeQuoteHash(sampleQuote, "test_secret_key");
    const hash2 = computeQuoteHash(sampleQuote, "test_secret_key");
    assert.equal(hash1, hash2);
    assert.equal(hash1.length, 64);
  });

  it("should verify valid quote hash and reject tampered quote", () => {
    const hash = computeQuoteHash(sampleQuote, "test_secret_key");
    assert.equal(verifyQuoteHash(sampleQuote, hash, "test_secret_key"), true);

    const tamperedQuote = { ...sampleQuote, offeredUnitPricePaise: 100000 };
    assert.equal(verifyQuoteHash(tamperedQuote, hash, "test_secret_key"), false);
  });

  it("should sign lock payload with Ed25519 and verify detached signature", () => {
    const keyPair = generateEd25519KeyPair();
    const lockPayload = {
      lockToken: "3f9d45e2-658b-4781-80a1-6a2c20a4bdf1",
      fencingToken: 1042,
      skuId: "SKU-CHAIR-001",
      quantityLocked: 2,
      expiresAtUnixMs: Date.now() + 60000
    };

    const signature = signLockPayload(lockPayload, keyPair.secretKeyHex);
    assert.ok(signature.length > 0);

    const isValid = verifyLockSignature(lockPayload, signature, keyPair.secretKeyHex);
    assert.equal(isValid, true);

    const tamperedLock = { ...lockPayload, quantityLocked: 100 };
    const isTamperedValid = verifyLockSignature(tamperedLock, signature, keyPair.secretKeyHex);
    assert.equal(isTamperedValid, false);
  });
});
