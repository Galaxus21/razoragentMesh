// The pincode -> state map is the single input that decides CGST+SGST versus IGST, and it is
// duplicated across two languages with no shared source of truth. These tests pin the three
// things the dress rehearsal found wrong: an unmapped prefix was silently taxed as the merchant's
// own state, the shipping path disagreed with the tax path about the same pincode, and the TS map
// was missing nineteen prefixes the Python engine already knew.

import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { executeSkuQuote, lookupStateFromPincode, resolveStateFromPincode } from "../src/tools/skuQuoter.js";
import { resolveZoneCode } from "../src/tools/slaVerifier.js";
import { pincodePrefixStateMap } from "../src/constants/protocolConstants.js";

const unmappedPincode = "999001";
const goaPincode = "403001";

describe("delivery state resolution", () => {
  it("refuses an unmapped prefix instead of taxing it as the merchant's own state", () => {
    // defaultFallbackState was "KA" and defaultMerchantState is "KA", so an unmapped prefix took
    // the intra-state branch and issued CGST+SGST for a delivery that could be anywhere in India.
    assert.throws(
      () => resolveStateFromPincode(unmappedPincode),
      /no GST state is registered for the prefix '99'/
    );
  });

  it("refuses the whole quote rather than returning a silently guessed tax head", () => {
    assert.throws(
      () =>
        executeSkuQuote({
          sku_id: "SKU-CHAIR-001",
          quantity: 1,
          buyer_agent_id: "did:agent:enterprise-procure-01",
          delivery_pincode: unmappedPincode
        }),
      /INVALID_PINCODE|Invalid delivery pincode/
    );
  });

  it("resolves the prefixes that were missing from the TypeScript map", () => {
    // Ported from the engine's pinPrefixToStateCode, which already knew all of these.
    assert.equal(lookupStateFromPincode("171001"), "HP");
    assert.equal(lookupStateFromPincode("190001"), "JK");
    assert.equal(lookupStateFromPincode("452001"), "MP");
    assert.equal(lookupStateFromPincode("492001"), "CG");
    assert.equal(lookupStateFromPincode("751001"), "OD");
    assert.equal(lookupStateFromPincode("781001"), "AS");
    assert.equal(lookupStateFromPincode("800001"), "BR");
    assert.equal(lookupStateFromPincode("834001"), "JH");
  });

  it("agrees with the mandate engine on which prefixes are serviceable", () => {
    // No shared fixture exists between the two maps, so read the engine's map directly. A prefix
    // the engine accepts but the mesh does not is a quote that dies at settlement; the reverse is
    // a quote the mesh prices and the engine then refuses with InvalidPincodeException.
    const enginePath = fileURLToPath(
      new URL("../../mandateEngine/tax/stateCodeMapping.py", import.meta.url)
    );
    const enginePrefixes = new Set(
      [...readFileSync(enginePath, "utf-8").matchAll(/^\s*"(\d{2})":\s*"\d{2}",/gm)].map((m) => m[1])
    );
    const meshPrefixes = new Set(Object.keys(pincodePrefixStateMap));

    assert.ok(enginePrefixes.size > 0, "the engine map must have been parsed");
    const missingFromMesh = [...enginePrefixes].filter((p) => !meshPrefixes.has(p)).sort();
    const missingFromEngine = [...meshPrefixes].filter((p) => !enginePrefixes.has(p)).sort();
    assert.deepEqual(missingFromMesh, [], "prefixes the engine accepts but the mesh cannot quote");
    assert.deepEqual(missingFromEngine, [], "prefixes the mesh quotes but the engine refuses");
  });
});

describe("shipping zone resolution", () => {
  it("uses the same lookup as the tax path rather than falling through to the raw prefix", () => {
    // An unmapped delivery is ZONE_D -- "the mesh does not know where this is" -- rather than the
    // raw prefix string, which could never equal the origin state and so read as an ordinary
    // out-of-state delivery the mesh would happily price.
    assert.equal(resolveZoneCode("560001", unmappedPincode), "ZONE_D");
    assert.equal(resolveZoneCode("560001", "560034"), "ZONE_A");
    assert.equal(resolveZoneCode("560001", "570001"), "ZONE_B");
    assert.equal(resolveZoneCode("560001", "400001"), "ZONE_C");
  });

  it("records that two-digit granularity misfiles Goa as Maharashtra", () => {
    // Goa is 403xxx and shares the "40" prefix with Mumbai. Both maps therefore report
    // Maharashtra (GST 27) for a Goa delivery, where the correct code is 30. Correcting it needs
    // three-digit granularity in both languages; until then this pins the known-wrong answer so
    // the limitation cannot be forgotten, and so a future fix has to update this test.
    assert.equal(lookupStateFromPincode(goaPincode), "MH");
  });
});
