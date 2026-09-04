import { describe, it } from "node:test";
import assert from "node:assert/strict";
import React from "react";

import {
  navigationCategories,
  navigationItems,
  NavCategoryConfig,
} from "../src/components/appSidebar.js";
import { loadDocPage } from "../src/lib/docsLoader.js";

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
    const unknownRoutes = ["/unknown-page", "/admin", "/login", "/api/v1/telemetry"];
    for (const unknownRoute of unknownRoutes) {
      assert.equal(findCategoryForRoute(unknownRoute), undefined);
    }

    // /docs/unknown is the exception, and deliberately so since /docs became a real route:
    // a missing guide is still somewhere in the documentation, and leaving the sidebar with
    // nothing lit told the reader they had left the section rather than mistyped a page.
    assert.equal(findCategoryForRoute("/docs/unknown")?.id, "documentation");
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
  // These now assert against the .mdx source through the loader rather than against a rendered
  // element tree. The facts under test are properties of the documentation, not of a React
  // component, and the six per-guide page components they used to render no longer exist --
  // one [...slug] route serves every guide.
  function readDocBody(slug: string): string {
    const page = loadDocPage([slug]);
    assert.ok(page, `Documentation page ${slug} did not load`);
    return page.body;
  }

  it("should verify the setup guide contains required enclave configuration content", () => {
    const body = readDocBody("setup");
    assert.ok(body.includes("docker compose up -d --build"), "Missing docker compose command");
    assert.ok(body.includes("http://localhost:8000/health"), "Missing health endpoint url");
    // Was AP2_GATE_DAILY_LIMIT_PAISE, which no code has ever read. Asserting a guide mentions a
    // phantom variable is how the guide stayed wrong: the test protected the mistake. This one is
    // the key docker-compose actually interpolates into the MCP server.
    assert.ok(body.includes("MERCHANT_PRIVATE_KEY_HEX"), "Missing merchant signing key variable");
  });

  it("should verify the buyer SDK guide contains required AP2 protocol and SLA content", () => {
    const body = readDocBody("buyer-sdk");
    // Was three INV-xx codes. Two of them named the wrong guarantee against the invariant table
    // this page's reader would have looked them up in, and the test still passed -- a substring
    // match on an identifier says nothing about whether the subject is still covered. These
    // assert the sections themselves.
    assert.ok(body.includes("The AP2 mandate chain"), "Missing the mandate chain section");
    assert.ok(
      body.includes("Negotiation and amendments"),
      "Missing the monotonic concession section"
    );
    assert.ok(
      body.includes("Inventory locks and fencing tokens"),
      "Missing the inventory fencing section"
    );
  });

  it("should verify the merchant guide contains required statutory HSN and bullion content", () => {
    const body = readDocBody("merchant-guide");
    for (const hsnCode of ["7113", "6109", "3004", "8471"]) {
      assert.ok(body.includes(hsnCode), `Missing HSN ${hsnCode}`);
    }
    assert.ok(
      body.includes("HSN codes and tax rates"),
      "Missing the statutory tax rules section"
    );
    assert.ok(body.includes("Bullion pricing"), "Missing the bullion pricing section");
  });

  it("should give every guide the frontmatter the pipeline depends on", () => {
    for (const slug of ["setup", "onboarding", "buyer-sdk", "merchant-guide", "telemetry", "gstr1-invoice"]) {
      const page = loadDocPage([slug]);
      assert.ok(page, `Documentation page ${slug} did not load`);
      assert.ok(page.frontmatter.title.length > 0, `${slug} has no title`);
      assert.ok(page.frontmatter.description.length > 0, `${slug} has no description`);
      assert.ok(page.frontmatter.navLabel.length > 0, `${slug} has no navLabel`);
      assert.ok(page.frontmatter.order > 0, `${slug} has no order`);
    }
  });
});
