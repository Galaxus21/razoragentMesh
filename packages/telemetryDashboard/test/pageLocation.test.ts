import { describe, it } from "node:test";
import assert from "node:assert/strict";

import { resolvePageLocation } from "../src/constants/sidebarNavigationConfig.js";

// The header names the page. Before this it printed "Autonomous Settlement Enclave / Razorpay
// Route Rails" on every screen -- a slogan that said the same thing on the merchant console, the
// docs and a live run, so it could not answer the one question a header exists to answer.

describe("The header names the page the reader is on", () => {
  it("resolves a section's landing tab, not just the section", () => {
    assert.deepEqual(resolvePageLocation("/visualise"), {
      title: "Live Agent",
      section: "Visualise",
    });
  });

  it("prefers the longest matching route, so a nested tab wins over its parent", () => {
    // /visualise/settle is a prefix match for BOTH /visualise and itself. Taking the first match
    // would label the settlement page "Live Agent".
    assert.deepEqual(resolvePageLocation("/visualise/settle"), {
      title: "Settle",
      section: "Visualise",
    });
    assert.equal(resolvePageLocation("/visualise/adversarial").title, "Adversarial");
    assert.equal(resolvePageLocation("/visualise/run").title, "Run It Here");
  });

  it("drops the section when it would only repeat the page name", () => {
    // Merchant is a one-page section, so "Merchant / Merchant" says nothing twice.
    assert.deepEqual(resolvePageLocation("/merchant-studio"), {
      title: "Merchant",
      section: null,
    });
    assert.deepEqual(resolvePageLocation("/overview"), { title: "Overview", section: null });
  });

  it("names an individual guide under Docs", () => {
    assert.deepEqual(resolvePageLocation("/docs/tool-reference"), {
      title: "Tool Reference",
      section: "Docs",
    });
    assert.deepEqual(resolvePageLocation("/docs"), { title: "All docs", section: "Docs" });
  });

  it("falls back to the product name on a route it does not know", () => {
    // A 404 still renders the shell, and a blank header there reads as a broken page.
    assert.deepEqual(resolvePageLocation("/nope"), {
      title: "RazorAgent Mesh",
      section: null,
    });
  });
});
