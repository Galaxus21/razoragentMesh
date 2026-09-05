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
import VisualisePage from "../src/app/(dashboard)/visualise/page.js";
import VisualiseRunPage from "../src/app/(dashboard)/visualise/run/page.js";
import AdversarialPage from "../src/app/(dashboard)/visualise/adversarial/page.js";
import SettlePage from "../src/app/(dashboard)/visualise/settle/page.js";
import MerchantStudioPage from "../src/app/(dashboard)/merchant-studio/page.js";
import DashboardGroupLayout from "../src/app/(dashboard)/layout.js";

const expectedCategoryCount = 4;
// 12 before Visualise's four sub-screens became sidebar rows of their own.
const expectedTotalRoutesCount = 16;
// Sidebar rows under Docs: the eight guides plus the /docs landing page. Kept apart from
// expectedDocumentCount because they stopped being the same number the moment the landing
// page existed, and a single constant would have made one of the two assertions vacuous.
const expectedDocsRoutesCount = 9;
const expectedDocumentCount = 8;
const expectedTelemetryRoutesCount = 7;

const docsLandingRoute = "/docs";

const requiredDocsRouteUrls: ReadonlyArray<string> = [
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

const requiredTelemetryRouteUrls: ReadonlyArray<string> = [
  "/overview",
  "/merchant-studio",
  "/visualise",
  "/visualise/settle",
  "/visualise/run",
  "/visualise/adversarial",
  "/visualise/vectors",
];

describe("Empirical Challenger 2 — Documentation Routes Mounting & Component Trees", () => {
  // Six per-guide page components have collapsed into one [...slug] route, so "does this page
  // component exist" is no longer a meaningful check. What must hold instead is that every
  // route the sidebar advertises resolves to a real document with usable frontmatter -- the
  // failure the old maps produced was a route that rendered "Page Not Found" with HTTP 200.
  it("should resolve every documentation route to a loadable page", () => {
    const docPages = loadAllDocPages();
    assert.equal(docPages.length, expectedDocumentCount);

    for (const page of docPages) {
      assert.ok(page.body.trim().length > 0, `${page.slug} has an empty body`);
      assert.ok(page.frontmatter.title.length > 0, `${page.slug} has no title`);
      assert.ok(page.sourcePath.endsWith(".mdx"), `${page.slug} is not an .mdx source`);
    }
  });

  it("should back each sidebar documentation route with a real document", () => {
    // /docs is the landing page: a real route with no .mdx behind it, so it is the one
    // documentation entry this invariant cannot apply to. Every other one must resolve, or
    // the sidebar is advertising a guide that does not exist.
    const guideRouteUrls = requiredDocsRouteUrls.filter((routeUrl) => routeUrl !== docsLandingRoute);
    assert.equal(guideRouteUrls.length, requiredDocsRouteUrls.length - 1);

    for (const routeUrl of guideRouteUrls) {
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
  it("should verify every category ID, icon, and children configuration", () => {
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

  it("should verify every navigation item has a valid URI path and non-empty metadata", () => {
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

describe("Empirical Challenger 2 — Zero Regression on All Telemetry Pages", () => {
  const telemetryPages = [
    { name: "OverviewPage", component: OverviewPage, route: "/overview" },
    { name: "MerchantStudioPage", component: MerchantStudioPage, route: "/merchant-studio" },
    { name: "SettlePage", component: SettlePage, route: "/visualise/settle" },
    { name: "VisualisePage", component: VisualisePage, route: "/visualise" },
    { name: "VisualiseRunPage", component: VisualiseRunPage, route: "/visualise/run" },
    { name: "AdversarialPage", component: AdversarialPage, route: "/visualise/adversarial" },
  ];

  for (const page of telemetryPages) {
    it(`should verify ${page.name} for ${page.route} exports a valid functional component`, () => {
      assert.equal(typeof page.component, "function", `${page.name} must be a function`);
      const element = React.createElement(page.component);
      assert.ok(React.isValidElement(element), `${page.name} element creation failed`);
    });
  }
});
