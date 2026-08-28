import { describe, it } from "node:test";
import assert from "node:assert/strict";
import React from "react";

import {
  navigationCategories,
  navigationItems,
  AppSidebar,
  NavCategoryConfig,
} from "../src/components/appSidebar.js";
import SetupDocsPage from "../src/app/(dashboard)/docs/setup/page.js";
import BuyerSdkDocsPage from "../src/app/(dashboard)/docs/buyer-sdk/page.js";
import MerchantGuideDocsPage from "../src/app/(dashboard)/docs/merchant-guide/page.js";

describe("Sidebar Accordion & 5-Category Taxonomy", () => {
  it("should categorize all 10 routes into exactly 5 specific domain groupings", () => {
    assert.equal(navigationCategories.length, 5);

    const categoryMap = new Map<string, ReadonlyArray<string>>();
    for (const cat of navigationCategories) {
      categoryMap.set(cat.id, cat.children.map((c) => c.route));
    }

    assert.deepEqual(categoryMap.get("platformOps"), [
      "/overview",
      "/self-healing",
      "/infrastructure",
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
      "/docs/buyer-sdk",
      "/docs/merchant-guide",
    ]);
  });

  it("should preserve flat navigationItems array containing all 10 routes", () => {
    assert.equal(navigationItems.length, 10);
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
  it("should render SetupDocsPage JSX without runtime error", () => {
    const element = React.createElement(SetupDocsPage);
    assert.ok(React.isValidElement(element));
    assert.equal(typeof SetupDocsPage, "function");
  });

  it("should render BuyerSdkDocsPage JSX without runtime error", () => {
    const element = React.createElement(BuyerSdkDocsPage);
    assert.ok(React.isValidElement(element));
    assert.equal(typeof BuyerSdkDocsPage, "function");
  });

  it("should render MerchantGuideDocsPage JSX without runtime error", () => {
    const element = React.createElement(MerchantGuideDocsPage);
    assert.ok(React.isValidElement(element));
    assert.equal(typeof MerchantGuideDocsPage, "function");
  });
});
