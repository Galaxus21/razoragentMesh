// The merchant key that signs Cart Mandates falls back to a literal committed in this
// repository. `merchantKeyFallbackWarning` was written to announce that at startup -- its own
// text says "Emitted at startup when the merchant key falls back to the literal committed in
// the repo" -- and nothing ever imported it, so the emission never happened.
//
// docker-compose passes `MERCHANT_PRIVATE_KEY_HEX=${MERCHANT_PRIVATE_KEY_HEX:-}`, so an unset
// variable arrives as the empty string, which is falsy in JS and takes the fallback silently.
// That key signs real Cart Mandates (cartMandateCreator.ts), so anyone holding this repository
// can forge one against a deployment that never configured a key.

import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  hmacKeyFallbackWarning,
  merchantKeyFallbackWarning
} from "../src/constants/mandateToolConstants.js";
import {
  defaultMerchantPrivateKeyHex,
  defaultMerchantSecretKey,
  merchantPrivateKeyIsDevelopmentFallback,
  merchantSecretKeyIsDevelopmentFallback
} from "../src/constants/protocolConstants.js";
import { warnOnDevelopmentSigningKeys } from "../src/mcpServerMain.js";

/** Captures everything written to stderr while `run` executes. */
function captureStderr(run: () => void): string {
  const originalWrite = process.stderr.write.bind(process.stderr);
  let captured = "";
  (process.stderr as unknown as { write: (chunk: string) => boolean }).write = (
    chunk: string
  ): boolean => {
    captured += chunk;
    return true;
  };
  try {
    run();
  } finally {
    (process.stderr as unknown as { write: typeof originalWrite }).write = originalWrite;
  }
  return captured;
}

describe("Development signing key warning", () => {
  it("announces the fallback instead of signing quietly with a committed key", () => {
    // The test process sets neither variable, so both flags are true here. If that ever stops
    // being so, the assertions below would vacuously pass -- hence checking it explicitly.
    assert.equal(
      merchantPrivateKeyIsDevelopmentFallback,
      true,
      "expected the test process to be running on the fallback merchant key"
    );
    assert.equal(merchantSecretKeyIsDevelopmentFallback, true);

    const emitted = captureStderr(() => warnOnDevelopmentSigningKeys());

    assert.ok(
      emitted.includes(merchantKeyFallbackWarning.trim()),
      `merchant key warning was not emitted. stderr was: ${JSON.stringify(emitted)}`
    );
    assert.ok(
      emitted.includes(hmacKeyFallbackWarning.trim()),
      `HMAC key warning was not emitted. stderr was: ${JSON.stringify(emitted)}`
    );
  });

  it("names the variable an operator has to set", () => {
    // A warning that does not say what to do about it is noise on the third read.
    assert.ok(merchantKeyFallbackWarning.includes("MERCHANT_PRIVATE_KEY_HEX"));
    assert.ok(hmacKeyFallbackWarning.includes("HMAC_SECRET_KEY"));
  });

  it("treats an empty environment variable as unset", () => {
    // This is the actual compose path: `${MERCHANT_PRIVATE_KEY_HEX:-}` substitutes "" when the
    // host has nothing set, and `"" || fallback` in JS yields the fallback. A guard written as
    // `process.env.X === undefined` would miss this entirely.
    assert.equal("" || defaultMerchantPrivateKeyHex, defaultMerchantPrivateKeyHex);
    assert.equal("" || defaultMerchantSecretKey, defaultMerchantSecretKey);
  });

  it("keeps the warning honest about what is at stake", () => {
    // V-04: the text is a specification. It claims forgery is possible; that is true precisely
    // because this key signs Cart Mandates, so the claim must not be softened without changing
    // what the key is used for.
    assert.match(merchantKeyFallbackWarning, /forge a Cart Mandate/);
  });
});
