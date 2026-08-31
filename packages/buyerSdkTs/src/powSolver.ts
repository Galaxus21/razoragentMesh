import { sha256Hex } from "./isomorphicCrypto.js";
import {
  defaultPowChunkSize,
  defaultPowDifficultyZeros,
  headerBuyerAgentDid,
  headerEscrowToken,
  headerPowChallenge,
  headerPowSolution,
} from "./sdkConstants.js";
import {
  PoWVerificationError,
  type PoWSolution,
  type PowVerificationResult
} from "./types.js";

export function solvePowChallenge(
  challengeToken: string,
  difficultyZeros: number = defaultPowDifficultyZeros
): PoWSolution {
  _validateChallengeToken(challengeToken);
  const startTime = Date.now();
  const targetPrefix = "0".repeat(difficultyZeros);
  let nonce = 0;

  while (true) {
    const candidateString = `${challengeToken}:${nonce}`;
    const digestHex = sha256Hex(candidateString);

    if (digestHex.startsWith(targetPrefix)) {
      return {
        nonce,
        computedDigest: digestHex,
        elapsedMs: Date.now() - startTime
      };
    }
    nonce += 1;
  }
}

export async function solvePowChallengeAsync(
  challengeToken: string,
  difficultyZeros: number = defaultPowDifficultyZeros,
  chunkSize: number = defaultPowChunkSize
): Promise<PoWSolution> {
  _validateChallengeToken(challengeToken);
  const startTime = Date.now();
  const targetPrefix = "0".repeat(difficultyZeros);
  let nonce = 0;

  return new Promise((resolve) => {
    function processChunk(): void {
      const endNonce = nonce + chunkSize;
      while (nonce < endNonce) {
        const candidateString = `${challengeToken}:${nonce}`;
        const digestHex = sha256Hex(candidateString);

        if (digestHex.startsWith(targetPrefix)) {
          resolve({
            nonce,
            computedDigest: digestHex,
            elapsedMs: Date.now() - startTime
          });
          return;
        }
        nonce += 1;
      }
      setImmediate(processChunk);
    }

    processChunk();
  });
}

export function verifyPowSolution(
  challengeToken: string,
  nonce: number,
  difficultyZeros: number = defaultPowDifficultyZeros
): PowVerificationResult {
  _validateChallengeToken(challengeToken);
  const targetPrefix = "0".repeat(difficultyZeros);
  const candidateString = `${challengeToken}:${nonce}`;
  const computedDigest = sha256Hex(candidateString);

  const isValid = computedDigest.startsWith(targetPrefix);
  return {
    isValid,
    challengeToken,
    computedDigest,
    errorMessage: isValid ? undefined : "Proof-of-work solution did not satisfy target difficulty"
  };
}

export function generatePowHeaders(
  challengeToken: string,
  solutionNonce: number,
  buyerAgentDid: string,
  escrowToken?: string
): Record<string, string> {
  const headers: Record<string, string> = {
    [headerPowChallenge]: challengeToken,
    [headerPowSolution]: solutionNonce.toString(),
    [headerBuyerAgentDid]: buyerAgentDid
  };

  if (escrowToken) {
    headers[headerEscrowToken] = escrowToken;
  }

  return headers;
}

function _validateChallengeToken(challengeToken: string): void {
  if (!challengeToken || typeof challengeToken !== "string" || challengeToken.trim().length === 0) {
    throw new PoWVerificationError("Challenge token must be a non-empty string");
  }
}
