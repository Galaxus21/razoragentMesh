import { describe, it } from "node:test";
import assert from "node:assert/strict";

import {
  navigationCategories,
  navigationItems,
} from "../src/components/appSidebar.js";
import {
  defaultSidebarCollapsed,
  sidebarStorageKey,
} from "../src/hooks/useSidebarState.js";
import { isRouteMatching } from "../src/constants/sidebarNavigationConfig.js";

const expectedRouteList: ReadonlyArray<string> = [
  "/overview",
  "/merchant-studio",
  "/visualise",
  "/visualise/settle",
  "/visualise/run",
  "/visualise/adversarial",
  "/visualise/vectors",
  "/docs",
  "/docs/setup",
  "/docs/agent-quickstart",
  "/docs/onboarding",
  "/docs/buyer-sdk",
  "/docs/merchant-guide",
  "/docs/tool-reference",
  "/docs/telemetry",
  "/docs/gstr1-invoice",
];

const expectedLabelList: ReadonlyArray<string> = [
  "Overview",
  "Merchant",
  "Live Agent",
  "Settle",
  "Run It Here",
  "Adversarial",
  "Vector Index",
  "All docs",
  "System Setup",
  "Agent Quickstart",
  "Developer Onboarding",
  "Buyer SDK",
  "Merchant Guide",
  "Tool Reference",
  "Telemetry & SSE",
  "GSTR-1 Invoicing",
];

const expectedCategoryIds: ReadonlyArray<string> = [
  "overview",
  "merchant",
  "visualise",
  "documentation",
];

const expectedCategoryLabels: ReadonlyArray<string> = [
  "Overview",
  "Merchant",
  "Visualise",
  "Docs",
];

describe("Milestone 2 — Sidebar State & Persistence Invariants", () => {
  it("should define correct localStorage key and default collapsed constant", () => {
    assert.equal(sidebarStorageKey, "razormesh-sidebar");
    assert.equal(defaultSidebarCollapsed, false);
  });

  it("should simulate storage reading and boolean serialization", () => {
    const simulateRead = (raw: string | null): boolean => {
      if (raw !== null) {
        return raw === "true";
      }
      return defaultSidebarCollapsed;
    };

    assert.equal(simulateRead("true"), true);
    assert.equal(simulateRead("false"), false);
    assert.equal(simulateRead(null), false);
    assert.equal(simulateRead("invalid"), false);
  });

  it("should simulate sidebar toggle state transitions", () => {
    let collapsed = defaultSidebarCollapsed;
    const toggle = () => {
      collapsed = !collapsed;
      return collapsed;
    };

    assert.equal(toggle(), true);
    assert.equal(toggle(), false);
    assert.equal(toggle(), true);
  });
});

describe("Milestone 2 — Navigation Categories & Accordion Hierarchy", () => {
  it("should define exactly 4 top-level navigation sections", () => {
    assert.equal(navigationCategories.length, 4);

    const categoryIds = navigationCategories.map((c) => c.id);
    assert.deepEqual(categoryIds, expectedCategoryIds);

    const categoryLabels = navigationCategories.map((c) => c.label);
    assert.deepEqual(categoryLabels, expectedCategoryLabels);

    for (const category of navigationCategories) {
      assert.ok(category.children.length > 0, `Category ${category.id} has no children`);
      assert.equal(typeof category.icon, "object", `Category ${category.id} icon must be defined`);
    }
  });

  it("should register every sidebar route exactly once", () => {
    // 12 before Visualise's four sub-screens became sidebar rows of their own.
    assert.equal(navigationItems.length, 16);

    const routes = navigationItems.map((item) => item.route);
    const uniqueRoutes = new Set(routes);
    assert.equal(uniqueRoutes.size, 16);

    for (const expectedRoute of expectedRouteList) {
      assert.ok(uniqueRoutes.has(expectedRoute), `Missing route: ${expectedRoute}`);
    }
  });

  it("should map descriptive labels and valid properties for every child item", () => {
    const labels = navigationItems.map((item) => item.label);
    for (let index = 0; index < expectedLabelList.length; index += 1) {
      assert.equal(labels[index], expectedLabelList[index]);
      assert.ok((navigationItems[index].description ?? "").length > 0);
    }
  });

  it("should correctly identify active routes with prefix matching", () => {
    // The shipped matcher, not a local copy. A private reimplementation here would keep
    // passing even if src/constants/sidebarNavigationConfig.ts were deleted outright.
    const isActiveRoute = isRouteMatching;

    assert.equal(isActiveRoute("/overview", "/overview"), true);
    assert.equal(isActiveRoute("/overview/details", "/overview"), true);
    assert.equal(isActiveRoute("/visualise", "/overview"), false);
    assert.equal(isActiveRoute("/visualise", "/visualise"), true);
    assert.equal(isActiveRoute("/merchant-studio", "/merchant-studio"), true);
    assert.equal(isActiveRoute("/docs/setup", "/docs/setup"), true);
    assert.equal(isActiveRoute("/docs/buyer-sdk", "/docs/buyer-sdk"), true);
    assert.equal(isActiveRoute("/docs/merchant-guide", "/docs/merchant-guide"), true);

    // A tab route belongs to itself alone, so the tab strip highlights exactly one page while
    // the sidebar's Visualise row stays lit by prefix.
    assert.equal(isActiveRoute("/visualise/adversarial", "/visualise/adversarial"), true);
    assert.equal(isActiveRoute("/visualise/adversarial", "/visualise"), false);
    assert.equal(isActiveRoute("/visualise/settle", "/visualise/settle"), true);
    assert.equal(isActiveRoute("/visualise/settle", "/visualise"), false);
  });
});
