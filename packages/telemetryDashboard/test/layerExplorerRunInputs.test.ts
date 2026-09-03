import { describe, it } from "node:test";
import assert from "node:assert/strict";

import {
  buildDefaultFormValues,
  runParameterFields,
} from "../src/constants/runParameterFields.js";
import {
  hasValidationErrors,
  notANumberMessage,
  notAnIntegerMessage,
  requiredMessage,
  validateRunParameters,
} from "../src/lib/runParameterValidation.js";
import {
  extractPackageName,
  listMeshPackages,
  summarisePackageUsage,
} from "../src/lib/packagePipeline.js";
import { defaultRunParameters } from "../src/server/protocolDriver/driverConfig.js";
import { protocolLayerNodes } from "../src/constants/protocolLayerMap.js";
import type { ProtocolStepRecord } from "../src/types/protocolRunTypes.js";

function buildStep(implementedBy: string, stepId: string): ProtocolStepRecord {
  return {
    stepId,
    ordinal: 1,
    title: "test step",
    narrative: "test narrative",
    protocolLayer: "Layer 1 - MCP discovery",
    implementedBy,
    sdkCall: { methodName: "test", argumentSummary: {}, isPureCrypto: false },
    status: "SUCCEEDED",
    durationMs: 1,
    exchanges: [],
    artifacts: [],
  };
}

describe("Layer Explorer — run inputs are the driver's own defaults", () => {
  // The form must never invent a default. If it did, a visitor pressing Run without editing
  // anything would silently execute a different run than the one the driver documents.
  it("should prefill every field from defaultRunParameters verbatim", () => {
    const values = buildDefaultFormValues();
    for (const field of runParameterFields) {
      const expected = defaultRunParameters[field.name];
      assert.equal(
        values[field.name],
        expected === undefined ? "" : String(expected),
        `Field ${field.name} was not prefilled from the driver default`
      );
    }
  });

  it("should cover every RunParameters key with exactly one descriptor", () => {
    const descriptorNames: ReadonlyArray<string> = runParameterFields
      .map((field) => String(field.name))
      .sort();
    const parameterNames = Object.keys(defaultRunParameters).sort();
    // promoCode is optional and absent from the defaults object, so it is checked separately
    // rather than by a naive key-for-key comparison.
    assert.ok(
      descriptorNames.includes("promoCode"),
      "promoCode must be editable even though it has no default"
    );
    for (const name of parameterNames) {
      assert.ok(descriptorNames.includes(name), `RunParameters key ${name} has no form field`);
    }
    assert.equal(new Set(descriptorNames).size, descriptorNames.length, "duplicate descriptor");
  });
});

describe("Layer Explorer — only edited fields become overrides", () => {
  it("should produce an empty override set for an untouched form", () => {
    const result = validateRunParameters(buildDefaultFormValues());
    assert.deepEqual(result.overrides, {});
    assert.deepEqual(result.changedFieldNames, []);
    assert.equal(hasValidationErrors(result), false);
  });

  it("should send only the field that was edited", () => {
    const values = { ...buildDefaultFormValues(), quantity: "4" };
    const result = validateRunParameters(values);
    assert.deepEqual(result.overrides, { quantity: 4 });
    assert.deepEqual(result.changedFieldNames, ["quantity"]);
  });

  it("should coerce numeric fields to numbers, not leave them as strings", () => {
    const values = { ...buildDefaultFormValues(), maxBudgetPaise: "12345" };
    const result = validateRunParameters(values);
    assert.strictEqual(result.overrides.maxBudgetPaise, 12345);
  });

  it("should treat a value edited back to its default as unchanged", () => {
    const values = { ...buildDefaultFormValues(), quantity: String(defaultRunParameters.quantity) };
    const result = validateRunParameters(values);
    assert.deepEqual(result.changedFieldNames, []);
  });
});

describe("Layer Explorer — validation refuses only what is plainly malformed", () => {
  it("should reject a non-numeric quantity", () => {
    const result = validateRunParameters({ ...buildDefaultFormValues(), quantity: "abc" });
    assert.equal(result.errors.quantity, notANumberMessage);
    assert.equal(hasValidationErrors(result), true);
  });

  it("should reject a fractional paise ceiling, because the enclave is integer-only", () => {
    const result = validateRunParameters({
      ...buildDefaultFormValues(),
      maxBudgetPaise: "100.5",
    });
    assert.equal(result.errors.maxBudgetPaise, notAnIntegerMessage);
  });

  it("should reject an out-of-range quantity with the declared bounds", () => {
    const field = runParameterFields.find((entry) => entry.name === "quantity");
    assert.ok(field?.minimum !== undefined && field?.maximum !== undefined);
    const result = validateRunParameters({
      ...buildDefaultFormValues(),
      quantity: String((field?.maximum ?? 0) + 1),
    });
    assert.ok(result.errors.quantity?.includes(String(field?.maximum)));
  });

  it("should reject a pincode that is not six digits", () => {
    const tooShort = validateRunParameters({
      ...buildDefaultFormValues(),
      deliveryPincode: "5600",
    });
    assert.ok(tooShort.errors.deliveryPincode);

    const notNumeric = validateRunParameters({
      ...buildDefaultFormValues(),
      deliveryPincode: "56003X",
    });
    assert.ok(notNumeric.errors.deliveryPincode);
  });

  it("should reject an emptied required field but allow an emptied optional one", () => {
    const emptiedRequired = validateRunParameters({ ...buildDefaultFormValues(), skuId: "" });
    assert.equal(emptiedRequired.errors.skuId, requiredMessage);

    const emptiedOptional = validateRunParameters({ ...buildDefaultFormValues(), promoCode: "" });
    assert.equal(emptiedOptional.errors.promoCode, undefined);
  });

  // A well-formed SKU that does not exist is the merchant's call, not the form's. Rejecting it
  // here would hide the real HTTP 404 the reader is supposed to see.
  it("should pass through a well-formed but unknown SKU id", () => {
    const result = validateRunParameters({
      ...buildDefaultFormValues(),
      skuId: "SKU-DOES-NOT-EXIST-999",
    });
    assert.equal(hasValidationErrors(result), false);
    assert.equal(result.overrides.skuId, "SKU-DOES-NOT-EXIST-999");
  });
});

describe("Layer Explorer — package attribution comes from the layer map", () => {
  it("should reduce a repository path to its package name", () => {
    assert.equal(extractPackageName("packages/mcpServer/src/tools/"), "mcpServer");
    assert.equal(
      extractPackageName("packages/buyerSdkTs/src/agentMandateBuilder.ts"),
      "buyerSdkTs"
    );
    assert.equal(extractPackageName("packages/vectorHealer"), "vectorHealer");
  });

  it("should return an unrecognised path unchanged rather than mangling it", () => {
    assert.equal(extractPackageName("scripts/seedTelemetryStream.py"), "scripts/seedTelemetryStream.py");
  });

  it("should derive its package roster from protocolLayerMap rather than a hand-written list", () => {
    const rosterNames = listMeshPackages().map((entry) => entry.packageName);
    const expected = new Set(
      protocolLayerNodes.flatMap((layer) => layer.implementedBy.map(extractPackageName))
    );
    assert.deepEqual(new Set(rosterNames), expected);
  });

  it("should report a zero count for a package the run never touched", () => {
    const usage = summarisePackageUsage([buildStep("packages/mcpServer/src/tools/", "a")]);
    const healer = usage.find((entry) => entry.packageName === "vectorHealer");
    assert.ok(healer, "vectorHealer must still appear so absence is visible, not silent");
    assert.equal(healer?.stepCount, 0);
  });

  it("should count repeated use of the same package", () => {
    const usage = summarisePackageUsage([
      buildStep("packages/mcpServer/src/tools/", "a"),
      buildStep("packages/mcpServer/src/http", "b"),
      buildStep("packages/mandateEngine/settlement/", "c"),
    ]);
    assert.equal(usage.find((entry) => entry.packageName === "mcpServer")?.stepCount, 2);
    assert.equal(usage.find((entry) => entry.packageName === "mandateEngine")?.stepCount, 1);
  });

  it("should surface a step whose package is absent from the layer map", () => {
    const usage = summarisePackageUsage([buildStep("packages/unlistedThing/src", "a")]);
    const unlisted = usage.find((entry) => entry.packageName === "unlistedThing");
    assert.ok(unlisted, "an unmapped package must not vanish from the strip");
    assert.equal(unlisted?.stepCount, 1);
  });
});
