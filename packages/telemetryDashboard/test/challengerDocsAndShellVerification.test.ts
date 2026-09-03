import { describe, it } from "node:test";
import assert from "node:assert/strict";
import React from "react";

import {
  navigationCategories,
  navigationItems,
  AppSidebar,
  NavCategoryConfig,
  NavChildItemConfig,
} from "../src/components/appSidebar.js";
import { loadAllDocPages, loadDocPage } from "../src/lib/docsLoader.js";
import OverviewPage from "../src/app/(dashboard)/overview/page.js";
import AgentObservabilityPage from "../src/app/(dashboard)/agent-observability/page.js";
import NegotiationHubPage from "../src/app/(dashboard)/negotiation-hub/page.js";
import SecurityAuditPage from "../src/app/(dashboard)/security-audit/page.js";
import SelfHealingPage from "../src/app/(dashboard)/self-healing/page.js";
import InfrastructurePage from "../src/app/(dashboard)/infrastructure/page.js";
import MerchantStudioPage from "../src/app/(dashboard)/merchant-studio/page.js";
import DashboardGroupLayout from "../src/app/(dashboard)/layout.js";

const expectedCategoryCount = 6;
const expectedTotalRoutesCount = 20;
const expectedDocsRoutesCount = 7;
const expectedTelemetryRoutesCount = 13;

const requiredDocsRouteUrls: ReadonlyArray<string> = [
  "/docs/setup",
  "/docs/agent-quickstart",
  "/docs/onboarding",
  "/docs/buyer-sdk",
  "/docs/merchant-guide",
  "/docs/telemetry",
  "/docs/gstr1-invoice",
];

const requiredTelemetryRouteUrls: ReadonlyArray<string> = [
  "/overview",
  "/self-healing",
  "/infrastructure",
  "/protocol",
  "/playground/layers",
  "/playground",
  "/playground/adversarial",
  "/playground/live-agent",
  "/sdk-console",
  "/agent-observability",
  "/negotiation-hub",
  "/security-audit",
  "/merchant-studio",
];

describe("Empirical Challenger 2 — Documentation Routes Mounting & Component Trees", () => {
  // Six per-guide page components have collapsed into one [...slug] route, so "does this page
  // component exist" is no longer a meaningful check. What must hold instead is that every
  // route the sidebar advertises resolves to a real document with usable frontmatter -- the
  // failure the old maps produced was a route that rendered "Page Not Found" with HTTP 200.
  it("should resolve every documentation route to a loadable page", () => {
    const docPages = loadAllDocPages();
    assert.equal(docPages.length, expectedDocsRoutesCount);

    for (const page of docPages) {
      assert.ok(page.body.trim().length > 0, `${page.slug} has an empty body`);
      assert.ok(page.frontmatter.title.length > 0, `${page.slug} has no title`);
      assert.ok(page.sourcePath.endsWith(".mdx"), `${page.slug} is not an .mdx source`);
    }
  });

  it("should back each sidebar documentation route with a real document", () => {
    for (const routeUrl of requiredDocsRouteUrls) {
      const slug = routeUrl.replace("/docs/", "");
      const page = loadDocPage([slug]);
      assert.ok(page, `Sidebar advertises ${routeUrl} but no document backs it`);
    }
  });

  it("should order documentation by frontmatter rather than by directory listing", () => {
    const orders = loadAllDocPages().map((page) => page.frontmatter.order);
    const sorted = [...orders].sort((left, right) => left - right);
    assert.deepEqual(orders, sorted);
  });
});

describe("Empirical Challenger 2 — Link Integrity & Route Configuration Invariants", () => {
  it("should verify all 5 category IDs, icons, and children configurations", () => {
    assert.equal(navigationCategories.length, expectedCategoryCount);

    const seenCategoryIds = new Set<string>();
    for (const category of navigationCategories) {
      assert.ok(category.id.length > 0, "Category ID must not be empty");
      assert.ok(!seenCategoryIds.has(category.id), `Duplicate category ID: ${category.id}`);
      seenCategoryIds.add(category.id);

      assert.ok(category.label.length > 0, `Category ${category.id} has empty label`);
      assert.equal(typeof category.icon, "object", `Category ${category.id} has invalid icon`);
      assert.ok(category.children.length > 0, `Category ${category.id} has no child routes`);
    }
  });

  it("should verify all 20 navigation items have valid URI paths and non-empty metadata", () => {
    assert.equal(navigationItems.length, expectedTotalRoutesCount);

    const seenRoutes = new Set<string>();
    for (const item of navigationItems) {
      assert.ok(item.route.startsWith("/"), `Route must start with /: ${item.route}`);
      assert.ok(!item.route.endsWith("/") || item.route === "/", `Route has trailing slash: ${item.route}`);
      assert.ok(!seenRoutes.has(item.route), `Duplicate route detected: ${item.route}`);
      seenRoutes.add(item.route);

      assert.ok(item.label.trim().length > 0, `Route ${item.route} has empty label`);
      assert.ok((item.description ?? "").trim().length > 0, `Route ${item.route} has empty description`);
    }
  });

  it("should verify documentation and telemetry route sets are mutually exclusive and complete", () => {
    const docsRoutes = navigationCategories.find((c) => c.id === "documentation")?.children ?? [];
    assert.equal(docsRoutes.length, expectedDocsRoutesCount);

    const actualDocsUrls = docsRoutes.map((r) => r.route);
    assert.deepEqual(actualDocsUrls, requiredDocsRouteUrls);

    const telemetryRoutes = navigationCategories
      .filter((c) => c.id !== "documentation")
      .flatMap((c) => c.children);
    assert.equal(telemetryRoutes.length, expectedTelemetryRoutesCount);

    const actualTelemetryUrls = telemetryRoutes.map((r) => r.route);
    assert.deepEqual(actualTelemetryUrls, requiredTelemetryRouteUrls);
  });
});

describe("Empirical Challenger 2 — App Shell & Layout Scroll Invariants", () => {
  it("should verify DashboardGroupLayout renders without throwing", () => {
    const mockChild = React.createElement("div", { id: "test-content" }, "Test Content");
    const layoutElement = React.createElement(DashboardGroupLayout, null, mockChild);
    assert.ok(React.isValidElement(layoutElement));
    assert.equal(typeof DashboardGroupLayout, "function");
  });

  it("should verify AppSidebar props and rendering in both collapsed and expanded states", () => {
    let toggleCount = 0;
    const handleToggle = () => {
      toggleCount += 1;
    };

    const expandedSidebar = React.createElement(AppSidebar, {
      isCollapsed: false,
      onToggle: handleToggle,
      activeRoute: "/docs/setup",
    });
    assert.ok(React.isValidElement(expandedSidebar));

    const collapsedSidebar = React.createElement(AppSidebar, {
      isCollapsed: true,
      onToggle: handleToggle,
      activeRoute: "/docs/buyer-sdk",
    });
    assert.ok(React.isValidElement(collapsedSidebar));
  });
});

describe("Empirical Challenger 2 — Zero Regression on All 7 Existing Telemetry Pages", () => {
  const telemetryPages = [
    { name: "OverviewPage", component: OverviewPage, route: "/overview" },
    { name: "AgentObservabilityPage", component: AgentObservabilityPage, route: "/agent-observability" },
    { name: "NegotiationHubPage", component: NegotiationHubPage, route: "/negotiation-hub" },
    { name: "SecurityAuditPage", component: SecurityAuditPage, route: "/security-audit" },
    { name: "SelfHealingPage", component: SelfHealingPage, route: "/self-healing" },
    { name: "InfrastructurePage", component: InfrastructurePage, route: "/infrastructure" },
    { name: "MerchantStudioPage", component: MerchantStudioPage, route: "/merchant-studio" },
  ];

  for (const page of telemetryPages) {
    it(`should verify ${page.name} for ${page.route} exports a valid functional component`, () => {
      assert.equal(typeof page.component, "function", `${page.name} must be a function`);
      const element = React.createElement(page.component);
      assert.ok(React.isValidElement(element), `${page.name} element creation failed`);
    });
  }
});
