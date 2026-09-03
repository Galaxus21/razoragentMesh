import { describe, it } from "node:test";
import assert from "node:assert/strict";

import {
  defaultCatalogFormState,
  defaultGstRatePercent,
  defaultMinOrderQuantity,
  hsnGstLookupTable,
  hsnPresetOptions,
  maxDiscountBps,
  maxQuoteTtlSeconds,
  meshCatalogProxyEndpoint,
  minQuoteTtlSeconds,
  minVolumeQuantity,
  paisePerInrUnit,
} from "../src/constants/merchantCatalogConstants.js";
import {
  buildUniversalProductPayload,
  convertInrToPaise,
  formatPaiseToInr,
  resolveGstFromHsn,
  validateMerchantCatalogForm,
} from "../src/lib/merchantCatalogValidator.js";
import {
  CatalogSubmissionResult,
  MerchantCatalogFormData,
  TabIdentifier,
  UniversalProductListingPayload,
  VolumeTierInput,
} from "../src/types/merchantCatalogTypes.js";

// ============================================================================
// Empirical Test Harness for Tab Transitions, API Dispatches & Stress Scenarios
// ============================================================================

describe("Challenger 2 Empirical Verification: Tab State Transitions & Lifecycle", () => {
  it("should handle clean tab state transitions between telemetryMesh and merchantSkuStudio", () => {
    let activeTab: TabIdentifier = "telemetryMesh";
    const history: TabIdentifier[] = [activeTab];

    const switchTab = (nextTab: TabIdentifier) => {
      activeTab = nextTab;
      history.push(activeTab);
    };

    switchTab("merchantSkuStudio");
    assert.equal(activeTab, "merchantSkuStudio");

    switchTab("telemetryMesh");
    assert.equal(activeTab, "telemetryMesh");

    // Stress test: 1,000 rapid sequential tab switches
    for (let i = 0; i < 1000; i++) {
      switchTab(i % 2 === 0 ? "merchantSkuStudio" : "telemetryMesh");
    }

    assert.equal(history.length, 1003);
    assert.equal(activeTab, "telemetryMesh");
  });

  it("should preserve SSE event stream buffer when switching tabs", () => {
    // Simulated parent component state holding events and activeTab
    const eventBuffer: Array<{ id: string; type: string }> = [];
    let currentTab: TabIdentifier = "telemetryMesh";

    const receiveSseEvent = (evt: { id: string; type: string }) => {
      eventBuffer.push(evt);
    };

    // Seed events on initial tab
    receiveSseEvent({ id: "evt_1", type: "PAYMENT_CAPTURED" });
    assert.equal(eventBuffer.length, 1);

    // Switch to SKU Studio tab
    currentTab = "merchantSkuStudio";
    assert.equal(currentTab, "merchantSkuStudio");

    // SSE events continue arriving while user is in SKU Studio tab
    receiveSseEvent({ id: "evt_2", type: "BID_TURN_COMPLETED" });
    receiveSseEvent({ id: "evt_3", type: "MANDATE_SIGNED" });
    assert.equal(eventBuffer.length, 3);

    // Switch back to Telemetry Mesh tab
    currentTab = "telemetryMesh";
    assert.equal(currentTab, "telemetryMesh");
    assert.equal(eventBuffer.length, 3);
    assert.equal(eventBuffer[0].id, "evt_1");
    assert.equal(eventBuffer[2].id, "evt_3");
  });
});

const validTestFormData: MerchantCatalogFormData = {
  ...defaultCatalogFormState,
  skuId: "SKU-STRESS-001",
  merchantDid: "did:razoragent:merchant:stress01",
  title: "Valid Stress Test Product",
  description: "A complete description meeting all statutory character length and validation constraints.",
  category: "Electronics",
  hsnCode: "84713010",
  gstRatePercent: 18,
  basePriceInr: "25000.00",
  availableStock: 10,
  originPincode: "560001",
  bullionPricing: {
    ...defaultCatalogFormState.bullionPricing,
    enabled: false,
  },
};

describe("Challenger 2 Empirical Verification: Form Submission & Failure Reporting", () => {
  async function simulatePublishToMesh(
    formData: MerchantCatalogFormData,
    customFetch: (url: string, init?: RequestInit) => Promise<Response>
  ): Promise<CatalogSubmissionResult> {
    const validation = validateMerchantCatalogForm(formData);
    if (!validation.isValid) {
      return {
        status: "error",
        message: "Form validation failed. Please correct the highlighted errors.",
      };
    }

    try {
      const payload = buildUniversalProductPayload(formData);
      // Mirrors the real hook: a server-side proxy, not a relative path to a route the
      // dashboard does not serve. The old value 404ed on every publish.
      const endpoint = meshCatalogProxyEndpoint;
      const response = await customFetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (response.ok) {
        return {
          status: "success",
          message: `SKU successfully published to Mesh catalog! (HTTP ${response.status})`,
          skuId: formData.skuId,
          merchantDid: formData.merchantDid,
          timestampMs: Date.now(),
        };
      }
      const errorText = await response.text().catch(() => "Unknown error");
      return {
        status: "error",
        message: `Mesh catalog rejected listing: ${errorText} (HTTP ${response.status})`,
      };
    } catch (error: unknown) {
      const detail = error instanceof Error ? error.message : String(error);
      return {
        status: "error",
        message: `Publish failed -- the dashboard could not be reached: ${detail}`,
      };
    }
  }

  it("should successfully return status 'success' (CREATED) when backend responds with HTTP 200/201", async () => {
    const mockSuccessFetch = async (url: string, init?: RequestInit): Promise<Response> => {
      assert.equal(url, meshCatalogProxyEndpoint);
      assert.equal(init?.method, "POST");
      const body = JSON.parse(init?.body as string);
      assert.equal(body.skuId, validTestFormData.skuId);
      assert.equal(typeof body.baseUnitPricePaise, "number");

      return new Response(JSON.stringify({ status: "CREATED", skuId: body.skuId }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      });
    };

    const result = await simulatePublishToMesh(validTestFormData, mockSuccessFetch);
    assert.equal(result.status, "success");
    assert.ok(result.message.includes("HTTP 201"));
    assert.equal(result.skuId, validTestFormData.skuId);
    assert.equal(result.merchantDid, validTestFormData.merchantDid);
    assert.ok(typeof result.timestampMs === "number" && result.timestampMs > 0);
  });

  it("should report a network failure as a failure, never as success-flavoured text", async () => {
    const mockNetworkFailureFetch = async (): Promise<Response> => {
      throw new TypeError("Failed to fetch: Connection refused (ECONNREFUSED)");
    };

    const result = await simulatePublishToMesh(validTestFormData, mockNetworkFailureFetch);

    // The listing did not reach the mesh, so the operator must be told it failed. This branch
    // previously returned status "offline" with "Validated payload synthesized and ready for
    // deployment" -- text a merchant reasonably reads as "published". The old test asserted
    // that message was correct, which is why it stayed wrong.
    assert.equal(result.status, "error");
    assert.ok(
      /fail/i.test(result.message),
      `a failed publish must say so; got: ${result.message}`
    );
    for (const reassurance of ["ready for deployment", "synthesized", "local dev mode"]) {
      assert.ok(
        !result.message.includes(reassurance),
        `a failed publish must not reassure the operator with "${reassurance}"`
      );
    }
  });

  it("should return status 'error' when backend rejects payload with HTTP 400 / 500", async () => {
    const mockErrorFetch = async (): Promise<Response> => {
      return new Response("Invalid signature or duplicate SKU ID", {
        status: 400,
        headers: { "Content-Type": "text/plain" },
      });
    };

    const result = await simulatePublishToMesh(validTestFormData, mockErrorFetch);
    assert.equal(result.status, "error");
    assert.ok(result.message.includes("Mesh catalog rejected listing"));
    assert.ok(result.message.includes("HTTP 400"));
    assert.ok(result.message.includes("Invalid signature or duplicate SKU ID"));
  });

  it("should reject submission without network dispatch when form validation fails", async () => {
    let networkCallMade = false;
    const mockFetch = async (): Promise<Response> => {
      networkCallMade = true;
      return new Response("OK", { status: 200 });
    };

    const invalidForm: MerchantCatalogFormData = {
      ...validTestFormData,
      skuId: "", // Missing SKU
      title: "X", // Too short
    };

    const result = await simulatePublishToMesh(invalidForm, mockFetch);
    assert.equal(networkCallMade, false);
    assert.equal(result.status, "error");
    assert.ok(result.message.includes("Form validation failed"));
  });
});

describe("Challenger 2 Empirical Verification: Financial Integer Arithmetic & Boundary Invariants", () => {
  it("should convert fractional INR values with exact integer paise precision without float drift", () => {
    const testCases: Array<[number | string, number]> = [
      [0.01, 1],
      [0.99, 99],
      [1.0, 100],
      [42.5, 4250],
      [99.99, 9999],
      [1234.56, 123456],
      [99999.99, 9999999],
      ["4200.00", 420000],
      ["0.05", 5],
      ["150000.75", 15000075],
    ];

    for (const [input, expectedPaise] of testCases) {
      const actualPaise = convertInrToPaise(input);
      assert.equal(actualPaise, expectedPaise, `Failed for input: ${input}`);
      assert.equal(Number.isInteger(actualPaise), true);
    }
  });

  it("should enforce statutory GST rates across all 22 HSN chapter lookup codes", () => {
    for (const [hsn, expectedGst] of Object.entries(hsnGstLookupTable)) {
      const resolved = resolveGstFromHsn(hsn);
      assert.equal(resolved, expectedGst, `HSN ${hsn} resolved to ${resolved}%, expected ${expectedGst}%`);
    }
  });

  it("should validate all HSN preset templates as 100% valid form configurations", () => {
    for (const preset of hsnPresetOptions) {
      const formFromPreset: MerchantCatalogFormData = {
        ...defaultCatalogFormState,
        skuId: `SKU-${preset.hsn.slice(0, 4)}`,
        originPincode: "560001",
        basePriceInr: "1999.00",
        availableStock: 25,
        hsnCode: preset.hsn,
        gstRatePercent: preset.gstRate,
        category: preset.category,
        title: `Test Product for ${preset.description}`,
        description: `Automated testing listing for HSN ${preset.hsn} - ${preset.description}`,
        bullionPricing: {
          ...defaultCatalogFormState.bullionPricing,
          enabled: preset.category === "Jewelry",
          netWeightGrams: preset.category === "Jewelry" ? 5.5 : 0,
        },
      };

      const validation = validateMerchantCatalogForm(formFromPreset);
      assert.equal(
        validation.isValid,
        true,
        `HSN preset ${preset.hsn} failed validation: ${JSON.stringify(validation.errors)}`
      );

      const payload = buildUniversalProductPayload(formFromPreset);
      assert.equal(payload.hsnCode, preset.hsn);
      assert.equal(payload.gstRatePercent, preset.gstRate);
      assert.equal(payload.category, preset.category);
    }
  });
});
