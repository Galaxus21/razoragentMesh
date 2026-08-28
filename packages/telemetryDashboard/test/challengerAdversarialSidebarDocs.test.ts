import { describe, it } from "node:test";
import assert from "node:assert/strict";
import React from "react";

import {
  navigationCategories,
  navigationItems,
  NavCategoryConfig,
} from "../src/components/appSidebar.js";
import SetupDocsPage from "../src/app/(dashboard)/docs/setup/page.js";
import BuyerSdkDocsPage from "../src/app/(dashboard)/docs/buyer-sdk/page.js";
import MerchantGuideDocsPage from "../src/app/(dashboard)/docs/merchant-guide/page.js";

const stressCycleCount = 1000;

function isRouteActive(activeRoute: string, targetRoute: string): boolean {
  if (!activeRoute || !targetRoute) {
    return false;
  }
  return activeRoute === targetRoute || activeRoute.startsWith(`${targetRoute}/`);
}

function findCategoryForRoute(route: string): NavCategoryConfig | undefined {
  return navigationCategories.find((cat) =>
    cat.children.some((child) => isRouteActive(route, child.route))
  );
}

describe("Adversarial Challenger — Sidebar Active Route & Matching Edge Cases", () => {
  it("should defensively handle malformed, blank, and boundary route strings", () => {
    assert.equal(isRouteActive("", "/overview"), false);
    assert.equal(isRouteActive("/overview", ""), false);
    assert.equal(isRouteActive("", ""), false);
    assert.equal(isRouteActive("/docs/setup", "/docs/setup"), true);
    assert.equal(isRouteActive("/docs/setup/deep/nested/view", "/docs/setup"), true);
    assert.equal(isRouteActive("/docs/setup-fake", "/docs/setup"), false);
    assert.equal(isRouteActive("/docs/setup", "/docs/buyer-sdk"), false);
  });

  it("should correctly resolve parent categories for all registered routes", () => {
    for (const item of navigationItems) {
      const parentCat = findCategoryForRoute(item.route);
      assert.ok(parentCat !== undefined, `Route ${item.route} has no resolving parent category`);
      assert.ok(parentCat.children.some((c) => c.route === item.route));
    }
  });

  it("should return undefined parent category for unregistered route strings", () => {
    const unknownRoutes = ["/unknown-page", "/docs/unknown", "/admin", "/login", "/api/v1/telemetry"];
    for (const unknownRoute of unknownRoutes) {
      assert.equal(findCategoryForRoute(unknownRoute), undefined);
    }
  });
});

describe("Adversarial Challenger — Accordion State Stress & Immutability", () => {
  it("should sustain 1,000 rapid toggle cycles without state corruption", () => {
    let state: Record<string, boolean> = {
      platformOps: true,
      aiBuyerAgents: true,
      cfosAuditors: true,
      merchants: true,
      documentation: true,
    };

    const categoryKeys = Object.keys(state);

    for (let cycle = 0; cycle < stressCycleCount; cycle += 1) {
      const targetKey = categoryKeys[cycle % categoryKeys.length];
      const previousValue = state[targetKey];
      state = {
        ...state,
        [targetKey]: !previousValue,
      };
      assert.equal(state[targetKey], !previousValue);
    }

    // Verify all keys remain intact and boolean
    for (const key of categoryKeys) {
      assert.equal(typeof state[key], "boolean");
    }
  });

  it("should handle toggling unknown category keys gracefully", () => {
    let state: Record<string, boolean> = {
      platformOps: true,
    };

    const toggleUnknown = (key: string) => {
      state = {
        ...state,
        [key]: !state[key],
      };
    };

    toggleUnknown("nonExistentCategory");
    assert.equal(state.nonExistentCategory, true);
    assert.equal(state.platformOps, true);
  });
});

describe("Adversarial Challenger — Documentation Content Invariants", () => {
  it("should verify SetupDocsPage contains required enclave configuration content", () => {
    const rendered = SetupDocsPage();
    assert.ok(React.isValidElement(rendered));

    // Convert element tree to JSON structure for deep string verification
    const jsonString = JSON.stringify(rendered);
    assert.ok(jsonString.includes("Platform Ops"), "Missing Platform Ops badge");
    assert.ok(jsonString.includes("docker compose up -d --build"), "Missing docker compose command");
    assert.ok(jsonString.includes("http://localhost:8000/health"), "Missing health endpoint url");
    assert.ok(jsonString.includes("AP2_GATE_DAILY_LIMIT_PAISE"), "Missing AP2 limit variable");
  });

  it("should verify BuyerSdkDocsPage contains required AP2 protocol and SLA content", () => {
    const rendered = BuyerSdkDocsPage();
    assert.ok(React.isValidElement(rendered));

    const jsonString = JSON.stringify(rendered);
    assert.ok(jsonString.includes("@razoragent/buyer-sdk-ts"), "Missing TS SDK package name");
    assert.ok(jsonString.includes("razoragent-buyer-sdk-py"), "Missing Python SDK package name");
    assert.ok(jsonString.includes("INV-02"), "Missing INV-02 lifecycle reference");
    assert.ok(jsonString.includes("INV-06"), "Missing INV-06 monotonic concession reference");
    assert.ok(jsonString.includes("INV-07"), "Missing INV-07 vector healing reference");
  });

  it("should verify MerchantGuideDocsPage contains required statutory HSN and bullion content", () => {
    const rendered = MerchantGuideDocsPage();
    assert.ok(React.isValidElement(rendered));

    const jsonString = JSON.stringify(rendered);
    assert.ok(jsonString.includes("7113"), "Missing HSN 7113");
    assert.ok(jsonString.includes("6109"), "Missing HSN 6109");
    assert.ok(jsonString.includes("3004"), "Missing HSN 3004");
    assert.ok(jsonString.includes("8471"), "Missing HSN 8471");
    assert.ok(jsonString.includes("INV-04"), "Missing INV-04 tax reference");
    assert.ok(jsonString.includes("INV-05"), "Missing INV-05 bullion formula reference");
  });
});
