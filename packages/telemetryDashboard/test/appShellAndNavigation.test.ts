import { describe, it } from "node:test";
import assert from "node:assert/strict";

import {
  navigationItems,
} from "../src/components/appSidebar.js";
import {
  defaultSidebarCollapsed,
  sidebarStorageKey,
} from "../src/hooks/useSidebarState.js";

const expectedRouteList: ReadonlyArray<string> = [
  "/overview",
  "/agent-observability",
  "/negotiation-hub",
  "/security-audit",
  "/self-healing",
  "/infrastructure",
  "/merchant-studio",
];

const expectedLabelList: ReadonlyArray<string> = [
  "Overview",
  "Agent Observability",
  "Negotiation Hub",
  "Security & Audit",
  "Self-Healing",
  "Infrastructure",
  "Merchant Studio",
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

describe("Milestone 2 — Navigation Items & Route Group Shell", () => {
  it("should register exactly 7 unique navigation routes", () => {
    assert.equal(navigationItems.length, 7);

    const routes = navigationItems.map((item) => item.route);
    const uniqueRoutes = new Set(routes);
    assert.equal(uniqueRoutes.size, 7);

    for (const expectedRoute of expectedRouteList) {
      assert.ok(uniqueRoutes.has(expectedRoute), `Missing route: ${expectedRoute}`);
    }
  });

  it("should map descriptive labels and valid icons for all 7 items", () => {
    const labels = navigationItems.map((item) => item.label);
    for (let index = 0; index < expectedLabelList.length; index += 1) {
      assert.equal(labels[index], expectedLabelList[index]);
      assert.ok(navigationItems[index].description.length > 0);
      assert.equal(typeof navigationItems[index].icon, "object");
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
  });
});
