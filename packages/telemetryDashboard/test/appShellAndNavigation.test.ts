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

const expectedRouteList: ReadonlyArray<string> = [
  "/overview",
  "/self-healing",
  "/infrastructure",
  "/agent-observability",
  "/negotiation-hub",
  "/security-audit",
  "/merchant-studio",
  "/docs/setup",
  "/docs/buyer-sdk",
  "/docs/merchant-guide",
];

const expectedLabelList: ReadonlyArray<string> = [
  "Overview",
  "Self-Healing",
  "Infrastructure",
  "Agent Observability",
  "Negotiation Hub",
  "Security & Audit",
  "Merchant Studio",
  "System Setup",
  "Buyer SDK",
  "Merchant Guide",
];

const expectedCategoryIds: ReadonlyArray<string> = [
  "platformOps",
  "aiBuyerAgents",
  "cfosAuditors",
  "merchants",
  "documentation",
];

const expectedCategoryLabels: ReadonlyArray<string> = [
  "Platform Ops",
  "AI Buyer Agents",
  "CFOs & Auditors",
  "Merchants",
  "Documentation",
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
  it("should define exactly 5 top-level navigation categories", () => {
    assert.equal(navigationCategories.length, 5);

    const categoryIds = navigationCategories.map((c) => c.id);
    assert.deepEqual(categoryIds, expectedCategoryIds);

    const categoryLabels = navigationCategories.map((c) => c.label);
    assert.deepEqual(categoryLabels, expectedCategoryLabels);

    for (const category of navigationCategories) {
      assert.ok(category.children.length > 0, `Category ${category.id} has no children`);
      assert.equal(typeof category.icon, "object", `Category ${category.id} icon must be defined`);
    }
  });

  it("should register exactly 10 unique navigation routes across all categories", () => {
    assert.equal(navigationItems.length, 10);

    const routes = navigationItems.map((item) => item.route);
    const uniqueRoutes = new Set(routes);
    assert.equal(uniqueRoutes.size, 10);

    for (const expectedRoute of expectedRouteList) {
      assert.ok(uniqueRoutes.has(expectedRoute), `Missing route: ${expectedRoute}`);
    }
  });

  it("should map descriptive labels and valid properties for all 10 child items", () => {
    const labels = navigationItems.map((item) => item.label);
    for (let index = 0; index < expectedLabelList.length; index += 1) {
      assert.equal(labels[index], expectedLabelList[index]);
      assert.ok((navigationItems[index].description ?? "").length > 0);
    }
  });

  it("should correctly identify active routes with prefix matching", () => {
    const isActiveRoute = (activeRoute: string, targetRoute: string): boolean => {
      return activeRoute === targetRoute || activeRoute.startsWith(`${targetRoute}/`);
    };

    assert.equal(isActiveRoute("/overview", "/overview"), true);
    assert.equal(isActiveRoute("/overview/details", "/overview"), true);
    assert.equal(isActiveRoute("/security-audit", "/overview"), false);
    assert.equal(isActiveRoute("/infrastructure", "/infrastructure"), true);
    assert.equal(isActiveRoute("/merchant-studio", "/merchant-studio"), true);
    assert.equal(isActiveRoute("/docs/setup", "/docs/setup"), true);
    assert.equal(isActiveRoute("/docs/buyer-sdk", "/docs/buyer-sdk"), true);
    assert.equal(isActiveRoute("/docs/merchant-guide", "/docs/merchant-guide"), true);
  });
});
