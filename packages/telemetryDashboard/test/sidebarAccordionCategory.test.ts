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

describe("Sidebar Accordion & 6-Category Taxonomy", () => {
  it("should categorize all 20 routes into exactly 6 specific domain groupings", () => {
    assert.equal(navigationCategories.length, 6);

    const categoryMap = new Map<string, ReadonlyArray<string>>();
    for (const cat of navigationCategories) {
      categoryMap.set(cat.id, cat.children.map((c) => c.route));
    }

    assert.deepEqual(categoryMap.get("platformOps"), [
      "/overview",
      "/self-healing",
      "/infrastructure",
    ]);

    // The protocol review surfaces are one section rather than being split across Platform Ops
    // and AI Buyer Agents, so a reviewer can read a layer and exercise it without switching
    // category. AI Buyer Agents keeps only the agent-behaviour views.
    assert.deepEqual(categoryMap.get("protocolPlayground"), [
      "/protocol",
      "/playground/layers",
      "/playground",
      "/playground/adversarial",
      "/playground/live-agent",
      "/sdk-console",
    ]);

    assert.deepEqual(categoryMap.get("aiBuyerAgents"), [
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
  "/docs/agent-quickstart",
      "/docs/onboarding",
      "/docs/buyer-sdk",
      "/docs/merchant-guide",
      "/docs/telemetry",
      "/docs/gstr1-invoice",
    ]);
  });

  it("should preserve flat navigationItems array containing all 20 routes", () => {
    assert.equal(navigationItems.length, 20);
    const flattenedRoutes = navigationCategories.flatMap((c) => c.children.map((ch) => ch.route));
    assert.deepEqual(navigationItems.map((i) => i.route), flattenedRoutes);
  });

  it("should simulate independent accordion toggle state logic", () => {
    let expandedCategories: Record<string, boolean> = {
      platformOps: true,
      protocolPlayground: true,
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
    assert.equal(expandedCategories.protocolPlayground, true);
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
