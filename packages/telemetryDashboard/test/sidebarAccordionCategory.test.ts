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

describe("Sidebar Accordion & 5-Category Taxonomy", () => {
  it("should categorize all 17 routes into exactly 5 specific domain groupings", () => {
    assert.equal(navigationCategories.length, 5);

    const categoryMap = new Map<string, ReadonlyArray<string>>();
    for (const cat of navigationCategories) {
      categoryMap.set(cat.id, cat.children.map((c) => c.route));
    }

    assert.deepEqual(categoryMap.get("platformOps"), [
      "/overview",
      "/protocol",
      "/self-healing",
      "/infrastructure",
    ]);

    assert.deepEqual(categoryMap.get("aiBuyerAgents"), [
      "/playground",
      "/playground/adversarial",
      "/sdk-console",
      "/agent-observability",
      "/negotiation-hub",
    ]);

    assert.deepEqual(categoryMap.get("cfosAuditors"), [
      "/security-audit",
    ]);

    assert.deepEqual(categoryMap.get("merchants"), [
      "/merchant-studio",
    ]);

    assert.deepEqual(categoryMap.get("documentation"), [
      "/docs/setup",
      "/docs/onboarding",
      "/docs/buyer-sdk",
      "/docs/merchant-guide",
      "/docs/telemetry",
      "/docs/gstr1-invoice",
    ]);
  });

  it("should preserve flat navigationItems array containing all 17 routes", () => {
    assert.equal(navigationItems.length, 17);
    const flattenedRoutes = navigationCategories.flatMap((c) => c.children.map((ch) => ch.route));
    assert.deepEqual(navigationItems.map((i) => i.route), flattenedRoutes);
  });

  it("should simulate independent accordion toggle state logic", () => {
    let expandedCategories: Record<string, boolean> = {
      platformOps: true,
      aiBuyerAgents: true,
      cfosAuditors: true,
      merchants: true,
      documentation: true,
    };

    const toggleCategory = (catId: string) => {
      expandedCategories = {
        ...expandedCategories,
        [catId]: !expandedCategories[catId],
      };
    };

    // Toggle platformOps closed
    toggleCategory("platformOps");
    assert.equal(expandedCategories.platformOps, false);
    assert.equal(expandedCategories.aiBuyerAgents, true);

    // Toggle documentation closed
    toggleCategory("documentation");
    assert.equal(expandedCategories.documentation, false);

    // Toggle platformOps open again
    toggleCategory("platformOps");
    assert.equal(expandedCategories.platformOps, true);
  });

  it("should simulate expand-from-collapsed interaction workflow", () => {
    let isCollapsed = true;
    let expandedCategories: Record<string, boolean> = {
      platformOps: false,
      aiBuyerAgents: false,
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
