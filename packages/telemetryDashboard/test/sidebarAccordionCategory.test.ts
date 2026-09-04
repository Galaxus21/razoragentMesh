import { describe, it } from "node:test";
import assert from "node:assert/strict";
import React from "react";

import {
  navigationCategories,
  navigationItems,
  AppSidebar,
  NavCategoryConfig,
} from "../src/components/appSidebar.js";
import { loadAllDocPages, loadDocPage } from "../src/lib/docsLoader.js";

describe("Sidebar Accordion & 4-Section Taxonomy", () => {
  it("should categorize every route into exactly 4 sections", () => {
    assert.equal(navigationCategories.length, 4);

    const categoryMap = new Map<string, ReadonlyArray<string>>();
    for (const cat of navigationCategories) {
      categoryMap.set(cat.id, cat.children.map((c) => c.route));
    }

    // The five single-panel routes -- Agent Observability, Negotiation Hub, Security & Audit,
    // Self-Healing and Infrastructure -- are gone as routes. Their panels render together on
    // /visualise, which is the screen a reader watches while an agent buys something.
    assert.deepEqual(categoryMap.get("overview"), ["/overview"]);
    assert.deepEqual(categoryMap.get("merchant"), ["/merchant-studio"]);
    assert.deepEqual(categoryMap.get("visualise"), ["/visualise"]);

    assert.deepEqual(categoryMap.get("documentation"), [
      "/docs",
      "/docs/setup",
  "/docs/agent-quickstart",
      "/docs/onboarding",
      "/docs/buyer-sdk",
      "/docs/merchant-guide",
      "/docs/tool-reference",
      "/docs/telemetry",
      "/docs/gstr1-invoice",
    ]);
  });

  it("should preserve flat navigationItems array containing every sidebar route", () => {
    assert.equal(navigationItems.length, 12);
    const flattenedRoutes = navigationCategories.flatMap((c) => c.children.map((ch) => ch.route));
    assert.deepEqual(navigationItems.map((i) => i.route), flattenedRoutes);
  });

  it("should simulate independent accordion toggle state logic", () => {
    let expandedCategories: Record<string, boolean> = {
      overview: true,
      merchant: true,
      visualise: true,
      documentation: true,
    };

    const toggleCategory = (catId: string) => {
      expandedCategories = {
        ...expandedCategories,
        [catId]: !expandedCategories[catId],
      };
    };

    // Toggle visualise closed
    toggleCategory("visualise");
    assert.equal(expandedCategories.visualise, false);
    assert.equal(expandedCategories.overview, true);
    assert.equal(expandedCategories.merchant, true);

    // Toggle documentation closed
    toggleCategory("documentation");
    assert.equal(expandedCategories.documentation, false);

    // Toggle visualise open again
    toggleCategory("visualise");
    assert.equal(expandedCategories.visualise, true);
  });

  it("should simulate expand-from-collapsed interaction workflow", () => {
    let isCollapsed = true;
    let expandedCategories: Record<string, boolean> = {
      visualise: false,
      merchant: false,
    };

    const handleExpandFromCollapsed = (catId: string) => {
      expandedCategories = {
        ...expandedCategories,
        [catId]: true,
      };
      isCollapsed = false;
    };

    handleExpandFromCollapsed("documentation");
    assert.equal(isCollapsed, false);
    assert.equal(expandedCategories.documentation, true);
  });
});

describe("Documentation Route Components Rendering", () => {
  it("should load every guide through the single documentation route", () => {
    // Previously three near-identical tests, one per hand-written doc page component. Those
    // components no longer exist; what matters now is that the loader finds each guide.
    const discovered = loadAllDocPages().map((page) => page.slug);
    for (const slug of ["setup", "buyer-sdk", "merchant-guide"]) {
      assert.ok(discovered.includes(slug), `Documentation page ${slug} was not discovered`);
      assert.ok(loadDocPage([slug]), `Documentation page ${slug} did not load`);
    }
  });

  it("should return null for a slug with no backing document", () => {
    assert.equal(loadDocPage(["no-such-guide"]), null);
  });
});
