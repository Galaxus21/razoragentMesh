import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  solvePowChallenge,
  solvePowChallengeAsync,
  verifyPowSolution,
  generatePowHeaders
} from "../src/powSolver.js";
import { PoWVerificationError } from "../src/types.js";
import {
  headerBuyerAgentDid,
  headerEscrowToken,
  headerPowChallenge,
  headerPowSolution
} from "../src/sdkConstants.js";

describe("powSolver", () => {
  it("should solve Proof-of-Work challenge with default difficulty (D=4)", () => {
    const challengeToken = "a1b2c3d4e5f60718293a4b5c6d7e8f90";
    const solution = solvePowChallenge(challengeToken, 4);

    assert.ok(typeof solution.nonce === "number");
    assert.ok(solution.nonce >= 0);
    assert.ok(solution.computedDigest.startsWith("0000"));
    assert.ok(solution.elapsedMs >= 0);

    const verification = verifyPowSolution(challengeToken, solution.nonce, 4);
    assert.equal(verification.isValid, true);
    assert.equal(verification.computedDigest, solution.computedDigest);
  });

  it("should solve challenges across varied difficulties (D=1 to D=4)", () => {
    const challengeToken = "challenge_matrix_test_token_123";

    for (let difficulty = 1; difficulty <= 4; difficulty += 1) {
      const solution = solvePowChallenge(challengeToken, difficulty);
      const prefix = "0".repeat(difficulty);
      assert.ok(solution.computedDigest.startsWith(prefix));

      const verification = verifyPowSolution(challengeToken, solution.nonce, difficulty);
      assert.equal(verification.isValid, true);
    }
  });

  it("should solve challenge asynchronously without blocking event loop", async () => {
    const challengeToken = "async_test_challenge_token_456";
    const solution = await solvePowChallengeAsync(challengeToken, 3, 500);

    assert.ok(solution.computedDigest.startsWith("000"));
    const verification = verifyPowSolution(challengeToken, solution.nonce, 3);
    assert.equal(verification.isValid, true);
  });

  it("should reject incorrect nonces in verifyPowSolution", () => {
    const challengeToken = "verify_test_token_789";
    const solution = solvePowChallenge(challengeToken, 3);

    const invalidVerification = verifyPowSolution(challengeToken, solution.nonce + 999999, 3);
    if (!invalidVerification.computedDigest.startsWith("000")) {
      assert.equal(invalidVerification.isValid, false);
      assert.ok(invalidVerification.errorMessage);
    }
  });

  it("should throw PoWVerificationError on invalid challenge token", () => {
    assert.throws(
      () => solvePowChallenge("", 4),
      (err: unknown) => err instanceof PoWVerificationError
    );

    assert.throws(
      () => solvePowChallenge("   ", 4),
      (err: unknown) => err instanceof PoWVerificationError
    );
  });

  it("should generate standard x402 PoW HTTP headers", () => {
    const challengeToken = "test_challenge_abc";
    const solutionNonce = 42891;
    const buyerDid = "did:agent:1111111111111111111111111111111111111111111111111111111111111111";
    const escrowToken = "escrow_session_tok_99";

    const headersWithEscrow = generatePowHeaders(challengeToken, solutionNonce, buyerDid, escrowToken);
    assert.equal(headersWithEscrow[headerPowChallenge], challengeToken);
    assert.equal(headersWithEscrow[headerPowSolution], "42891");
    assert.equal(headersWithEscrow[headerBuyerAgentDid], buyerDid);
    assert.equal(headersWithEscrow[headerEscrowToken], escrowToken);

    const headersNoEscrow = generatePowHeaders(challengeToken, solutionNonce, buyerDid);
    assert.equal(headersNoEscrow[headerPowChallenge], challengeToken);
    assert.equal(headersNoEscrow[headerEscrowToken], undefined);
  });
});
