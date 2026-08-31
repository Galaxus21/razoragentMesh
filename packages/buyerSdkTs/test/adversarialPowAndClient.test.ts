import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  solvePowChallenge,
  solvePowChallengeAsync,
  verifyPowSolution,
  generatePowHeaders
} from "../src/powSolver.js";
import { RazorAgentClient } from "../src/razorAgentClient.js";
import { AgentKeyManager } from "../src/agentKeyManager.js";
import { createSignedCartMandate } from "../src/agentMandateBuilder.js";
import { PoWVerificationError, ClientRequestError } from "../src/types.js";

describe("PoW Solver & RazorAgentClient Adversarial Stress Suite", () => {
  const buyerKeyManager = AgentKeyManager.generate();
  const merchantKeyManager = AgentKeyManager.generate();

  it("should handle D=0 and escalated D=5 PoW difficulty", async () => {
    const challengeD0 = "challenge_d0_test";
    const solutionD0 = solvePowChallenge(challengeD0, 0);
    assert.equal(solutionD0.nonce, 0);
    assert.equal(verifyPowSolution(challengeD0, 0, 0).isValid, true);

    const challengeD5 = "challenge_d5_escalated_test";
    const solutionD5 = await solvePowChallengeAsync(challengeD5, 5, 2000);
    assert.ok(solutionD5.computedDigest.startsWith("00000"));
    assert.equal(verifyPowSolution(challengeD5, solutionD5.nonce, 5).isValid, true);
  });

  it("should survive high concurrency PoW solving without race conditions", async () => {
    const concurrency = 25;
    const tasks = Array.from({ length: concurrency }, (_, index) => {
      const challenge = `concurrent_challenge_token_${index}_${Date.now()}`;
      const difficulty = 3;
      return solvePowChallengeAsync(challenge, difficulty, 500).then((solution) => {
        const verification = verifyPowSolution(challenge, solution.nonce, difficulty);
        return { index, valid: verification.isValid, digest: solution.computedDigest };
      });
    });

    const results = await Promise.all(tasks);
    assert.equal(results.length, concurrency);
    for (const res of results) {
      assert.equal(res.valid, true);
      assert.ok(res.digest.startsWith("000"));
    }
  });

  it("should throw PoWVerificationError for malformed challenge tokens", () => {
    assert.throws(() => solvePowChallenge("", 3), (e: unknown) => e instanceof PoWVerificationError);
    assert.throws(() => solvePowChallenge("   ", 3), (e: unknown) => e instanceof PoWVerificationError);
    assert.throws(() => verifyPowSolution("", 1, 3), (e: unknown) => e instanceof PoWVerificationError);
  });

  it("should handle non-200 HTTP responses in RazorAgentClient methods", async () => {
    const errorFetch: typeof fetch = async () => {
      return new Response("Internal Server Error", { status: 500, statusText: "Server Error" });
    };

    const client = new RazorAgentClient({ buyerKeyManager, customFetch: errorFetch });

    await assert.rejects(
      () => client.getLiveSkuQuote("SKU-FAIL-01", 1, { deliveryPincode: "560001" }),
      (err: unknown) => err instanceof ClientRequestError && err.statusCode === 500
    );

    await assert.rejects(
      () => client.reserveInventoryLock("SKU-FAIL-01", 1, { quoteHash: "qh_test" }),
      (err: unknown) => err instanceof ClientRequestError && err.statusCode === 500
    );

    await assert.rejects(
      () => client.verifyShippingSla("560001"),
      (err: unknown) => err instanceof ClientRequestError && err.statusCode === 500
    );
  });

  it("should propagate retry failures during HTTP 402 PoW negotiation", async () => {
    let callCount = 0;
    const retryFailFetch: typeof fetch = async () => {
      callCount += 1;
      if (callCount === 1) {
        return new Response(
          JSON.stringify({
            statusCode: 402,
            wwwAuthenticate: 'x402-INR tokenCostPaise="50"',
            challengeToken: "tok_retry_fail",
            powDifficultyZeros: 2
          }),
          { status: 402, headers: { "Content-Type": "application/json" } }
        );
      }
      return new Response("Forbidden after PoW", { status: 403 });
    };

    const client = new RazorAgentClient({ buyerKeyManager, customFetch: retryFailFetch });
    await assert.rejects(
      () => client.reserveInventoryLock("SKU-POW-FAIL", 1, { quoteHash: "qh_test" }),
      (err: unknown) => err instanceof ClientRequestError && err.statusCode === 403
    );
  });

  it("should clamp negative price drop concessions cleanly in handlePriceDropAlert", () => {
    const cartMandate = createSignedCartMandate(
      {
        merchantGstin: "29AABCU9603R1ZJ",
        merchantStateCode: "29",
        buyerDeliveryPincode: "560001",
        buyerDeliveryStateCode: "29",
        items: [
          {
            skuId: "SKU-CLAMP-1",
            quantity: 1,
            unitPricePaise: 50000,
            hsnCode: "8504",
            gstRatePercent: 18,
            lineTotalPaise: 50000
          }
        ],
        taxableSubtotalPaise: 50000,
        taxBreakdown: { cgstPaise: 4500, sgstPaise: 4500, igstPaise: 0, totalTaxPaise: 9000 },
        totalPaise: 59000,
        inventoryLockToken: "lock_clamp_1",
        inventoryLockExpiresAt: 1700000000
      },
      merchantKeyManager
    );

    const client = new RazorAgentClient({ buyerKeyManager });
    const negativeConcessionAlert = {
      skuId: "SKU-CLAMP-1",
      targetPricePaise: 60000,
      activePricePaise: 60000,
      concessionPaise: -5000
    };

    const amendment = client.handlePriceDropAlert(negativeConcessionAlert, cartMandate, merchantKeyManager);
    assert.equal(amendment.priceDeltaPaise, 0);
  });
});
