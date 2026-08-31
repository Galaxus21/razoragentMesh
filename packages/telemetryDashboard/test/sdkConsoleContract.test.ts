import { describe, it } from "node:test";
import assert from "node:assert/strict";

import {
  sdkMethodCatalog,
  sdkMethodsById,
} from "../src/constants/sdkConsoleCatalog.js";
import {
  buildDefaultParameterValues,
  validateSdkParameters,
} from "../src/lib/sdkParameterValidation.js";
import {
  InvalidSdkParametersError,
  UnknownSdkMethodError,
  invokeSdkMethod,
} from "../src/server/sdkConsole/invokeSdkMethod.js";
import { buildInvocationSnippets } from "../src/lib/snippetGenerator.js";
import type { WireExchange } from "../src/types/protocolRunTypes.js";

const quoteMethod = sdkMethodsById.getLiveSkuQuote;
const lockMethod = sdkMethodsById.reserveInventoryLock;

describe("SDK console catalog", () => {
  it("describes every method with a unique id and a documented parameter set", () => {
    const seenIds = new Set<string>();
    for (const method of sdkMethodCatalog) {
      assert.ok(!seenIds.has(method.methodId), `Duplicate methodId ${method.methodId}`);
      seenIds.add(method.methodId);

      assert.ok(method.parameters.length > 0, `${method.methodId} exposes no parameters`);
      assert.ok(method.summary.length > 0);
      assert.ok(method.transport.length > 0);
      assert.ok(method.implementedBy.startsWith("packages/"));

      for (const field of method.parameters) {
        assert.ok(field.helpText.length > 0, `${method.methodId}.${field.name} has no help text`);
        assert.ok(field.label.length > 0);
        if (field.isRequired) {
          assert.ok(
            field.defaultValue.length > 0,
            `Required field ${field.name} must ship a usable default`
          );
        }
      }
    }
  });

  it("warns before the one method that mutates server state", () => {
    // Reserving a lock decrements real stock. A visitor should learn that before pressing Send,
    // not by wondering why the catalog ran dry.
    assert.ok(lockMethod.sideEffectWarning);
    const readOnlyMethods = sdkMethodCatalog.filter(
      (method) => method.methodId !== "reserveInventoryLock"
    );
    for (const method of readOnlyMethods) {
      assert.equal(method.sideEffectWarning, undefined);
    }
  });

  it("ships defaults that pass its own validation, so the form is runnable unedited", () => {
    for (const method of sdkMethodCatalog) {
      const { violations } = validateSdkParameters(
        method,
        buildDefaultParameterValues(method)
      );
      assert.deepEqual(violations, [], `${method.methodId} ships defaults it would reject`);
    }
  });
});

describe("SDK console parameter validation", () => {
  it("rejects a missing required parameter and names the field", () => {
    const { violations } = validateSdkParameters(quoteMethod, {
      skuId: "",
      quantity: "2",
      deliveryPincode: "560034",
    });
    assert.equal(violations.length, 1);
    assert.equal(violations[0].fieldName, "skuId");
  });

  it("requires the delivery pincode the quote tool cannot price without", () => {
    // Optional in the SDK's QuoteOptions type, but the MCP tool returns HTTP 422 without it,
    // because it decides the CGST+SGST versus IGST split.
    const { violations } = validateSdkParameters(quoteMethod, {
      skuId: "SKU-CHAIR-001",
      quantity: "2",
    });
    assert.deepEqual(
      violations.map((violation) => violation.fieldName),
      ["deliveryPincode"]
    );
  });

  it("omits a blank optional parameter rather than sending an empty value", () => {
    // Sending promoCode="" would put an empty query parameter on the wire and stop the SDK
    // from applying its own default.
    const { violations, values } = validateSdkParameters(quoteMethod, {
      skuId: "SKU-CHAIR-001",
      quantity: "2",
      deliveryPincode: "560034",
      promoCode: "   ",
    });
    assert.deepEqual(violations, []);
    assert.equal("promoCode" in values, false);
  });

  it("refuses non-numeric, fractional and out-of-range numbers", () => {
    const nonNumeric = validateSdkParameters(quoteMethod, { skuId: "S", quantity: "abc" });
    assert.equal(nonNumeric.violations[0].fieldName, "quantity");

    const fractional = validateSdkParameters(quoteMethod, { skuId: "S", quantity: "1.5" });
    assert.equal(fractional.violations[0].fieldName, "quantity");

    const tooLarge = validateSdkParameters(quoteMethod, { skuId: "S", quantity: "9999" });
    assert.equal(tooLarge.violations[0].fieldName, "quantity");

    const tooSmall = validateSdkParameters(quoteMethod, { skuId: "S", quantity: "0" });
    assert.equal(tooSmall.violations[0].fieldName, "quantity");
  });

  it("coerces valid numbers to numbers and trims strings", () => {
    const { values } = validateSdkParameters(quoteMethod, {
      skuId: "  SKU-CHAIR-001  ",
      quantity: "3",
    });
    assert.equal(values.skuId, "SKU-CHAIR-001");
    assert.equal(values.quantity, 3);
  });
});

describe("SDK console invocation guards", () => {
  it("refuses an unknown method instead of attempting a call", async () => {
    await assert.rejects(
      () => invokeSdkMethod({ methodId: "dropAllTables", parameters: {} }),
      UnknownSdkMethodError
    );
  });

  it("validates on the server, so a hand-rolled request cannot bypass the form", async () => {
    // The endpoint is callable directly; the browser form is not the only entry point.
    await assert.rejects(
      () => invokeSdkMethod({ methodId: "reserveInventoryLock", parameters: { skuId: "" } }),
      InvalidSdkParametersError
    );
  });
});

describe("SDK console snippets", () => {
  it("derives the snippet from the recorded request rather than from the form", () => {
    const exchange: WireExchange = {
      method: "GET",
      url: "http://localhost:4001/api/v1/quote?skuId=SKU-CHAIR-001&quantity=4&deliveryPincode=560034",
      requestHeaders: { accept: "application/json" },
      requestBody: null,
      statusCode: 200,
      responseHeaders: {},
      responseBody: { skuId: "SKU-CHAIR-001" },
      durationMs: 12,
    };

    const snippets = buildInvocationSnippets("getLiveSkuQuote", [exchange]);
    const languages = snippets.map((snippet) => snippet.language);
    assert.deepEqual(languages, ["typescript", "python", "bash"]);

    for (const snippet of snippets) {
      assert.ok(
        snippet.code.includes("SKU-CHAIR-001"),
        `${snippet.language} snippet lost the recorded SKU`
      );
    }
    // The quantity shown must be the one that was actually sent, not the catalog default.
    assert.ok(snippets[0].code.includes("4"));
    assert.ok(snippets[2].code.startsWith("curl -X GET"));
  });

  it("degrades to a generic rendering for a method with no template", () => {
    const snippets = buildInvocationSnippets("someFutureMethod", []);
    assert.equal(snippets.length, 2);
    assert.ok(snippets[0].code.includes("someFutureMethod"));
  });
});

describe("SDK console prerequisite handling", () => {
  it("asks for everything the prerequisite quote needs before a lock", () => {
    // reserveInventoryLock cannot run alone: the MCP tool requires the quote_hash that binds
    // the reservation to a price. The console therefore fetches a quote first, which needs a
    // delivery pincode -- so the form must collect one.
    const parameterNames = lockMethod.parameters.map((field) => field.name);
    assert.ok(parameterNames.includes("deliveryPincode"));
    assert.ok(parameterNames.includes("skuId"));
    assert.ok(parameterNames.includes("quantity"));
    assert.ok(
      lockMethod.transport.includes("quote"),
      "The lock method must disclose that it also calls the quote endpoint"
    );
  });
});
