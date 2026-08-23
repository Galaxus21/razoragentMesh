export const minFencingTokenValue = 1;

export function isValidFencingToken(token: number): boolean {
  return typeof token === "number" && Number.isInteger(token) && token >= minFencingTokenValue;
}

export function validateFencingMonotonicity(
  newToken: number,
  previousToken: number
): boolean {
  if (!isValidFencingToken(newToken) || !isValidFencingToken(previousToken)) {
    return false;
  }
  return newToken > previousToken;
}

export function assertValidFencingToken(
  token: number,
  lastKnownToken?: number
): void {
  if (!isValidFencingToken(token)) {
    throw new Error(
      `Invalid fencing token: ${String(token)}. Must be an integer >= ${minFencingTokenValue}`
    );
  }

  if (lastKnownToken !== undefined && !validateFencingMonotonicity(token, lastKnownToken)) {
    throw new Error(
      `Fencing token regression detected: new token ${token} is not greater than previous token ${lastKnownToken}`
    );
  }
}
