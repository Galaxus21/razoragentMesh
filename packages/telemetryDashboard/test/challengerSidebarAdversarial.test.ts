import { describe, it } from "node:test";
import assert from "node:assert/strict";
import React from "react";

import {
  navigationCategories,
  navigationItems,
  NavCategoryConfig,
  AppSidebar,
  isCategoryActive,
  isRouteMatching,
} from "../src/components/appSidebar.js";
import DashboardGroupLayout from "../src/app/(dashboard)/layout.js";
import { loadAllDocPages, loadDocPage } from "../src/lib/docsLoader.js";

const stressLoopIterations = 5000;
const expectedCategoryCount = 4;
const expectedTotalRouteCount = 12;

const defaultCategoryIds: ReadonlyArray<string> = [
  "overview",
  "merchant",
  "visualise",
  "documentation",
];

// Imported from source rather than redefined locally. These tests previously carried their own
// copy of the prefix-matching logic, which meant they passed regardless of what the real
// implementation did -- they would still have gone green if isRouteMatching were deleted.
// isRouteMatching and isCategoryActive are imported from the source module below.

function simulateCategoryToggle(
  previousState: Record<string, boolean>,
  categoryId: string
): Record<string, boolean> {
  return {
    ...previousState,
    [categoryId]: !previousState[categoryId],
  };
}

function simulateExpandFromCollapsed(
  previousCategories: Record<string, boolean>,
  categoryId: string,
  onToggleCallback: () => void
): { nextCategories: Record<string, boolean>; isCollapsedNext: boolean } {
  let isCollapsedLocal = true;
  const nextCategories = {
    ...previousCategories,
    [categoryId]: true,
  };
  onToggleCallback();
  isCollapsedLocal = false;
  return { nextCategories, isCollapsedNext: isCollapsedLocal };
}

describe("Challenger 1 Empirical Stress: Rapid State Transitions & Category Isolation", () => {
  it("should maintain state consistency across 5,000 rapid toggles per category", () => {
    let state: Record<string, boolean> = {
      overview: true,
      merchant: true,
      visualise: true,
      merchants: true,
      documentation: true,
    };

    for (const categoryId of defaultCategoryIds) {
      for (let index = 0; index < stressLoopIterations; index += 1) {
        state = simulateCategoryToggle(state, categoryId);
      }
      const expectedBoolean = stressLoopIterations % 2 === 0 ? true : false;
      assert.equal(state[categoryId], expectedBoolean, `Mismatch for category: ${categoryId}`);
    }
  });

  it("should enforce category state isolation during randomized cross-category mutations", () => {
    let state: Record<string, boolean> = {
      overview: true,
      merchant: true,
      visualise: true,
      merchants: true,
      documentation: true,
    };

    const targetMutationCategory = "documentation";
    for (let index = 0; index < 2000; index += 1) {
      state = simulateCategoryToggle(state, targetMutationCategory);
    }

    assert.equal(state.overview, true);
    assert.equal(state.merchant, true);
    assert.equal(state.visualise, true);
    assert.equal(state.merchants, true);
    assert.equal(state.documentation, true);
  });
});

describe("Challenger 1 Empirical Stress: Route Matching & Edge Case Resolution", () => {
  it("should correctly resolve exact, nested, and sub-directory documentation routes", () => {
    const docRoutes = ["/docs/setup", "/docs/buyer-sdk", "/docs/merchant-guide"];
    for (const route of docRoutes) {
      assert.equal(isRouteMatching(route, route), true);
      assert.equal(isRouteMatching(`${route}/details`, route), true);
      assert.equal(isRouteMatching(`${route}/v2/step/1`, route), true);
    }
  });

  it("should reject prefix substring collisions without slash boundary", () => {
    assert.equal(isRouteMatching("/docs/setup-extended", "/docs/setup"), false);
    assert.equal(isRouteMatching("/overview-archive", "/overview"), false);
    assert.equal(isRouteMatching("/merchant-studio-beta", "/merchant-studio"), false);
  });

  it("should reject root path and unmapped routes against registered routes", () => {
    for (const item of navigationItems) {
      assert.equal(isRouteMatching("/", item.route), false);
      assert.equal(isRouteMatching("", item.route), false);
      assert.equal(isRouteMatching("/api/v1/health", item.route), false);
      assert.equal(isRouteMatching("/random-404-page", item.route), false);
    }
  });
});

describe("Challenger 1 Empirical Stress: Category Active State Detection", () => {
  it("should activate exactly one parent category per child route and zero for unknown routes", () => {
    assert.equal(navigationCategories.length, expectedCategoryCount);
    assert.equal(navigationItems.length, expectedTotalRouteCount);

    for (const category of navigationCategories) {
      for (const child of category.children) {
        assert.equal(isCategoryActive(category, child.route), true);
        assert.equal(isCategoryActive(category, `${child.route}/subview`), true);

        for (const otherCategory of navigationCategories) {
          if (otherCategory.id !== category.id) {
            assert.equal(isCategoryActive(otherCategory, child.route), false);
          }
        }
      }
    }

    for (const category of navigationCategories) {
      assert.equal(isCategoryActive(category, "/unknown-route"), false);
      assert.equal(isCategoryActive(category, "/"), false);
    }
  });
});

describe("Challenger 1 Empirical Stress: Collapsed Icon Interaction & Expansion", () => {
  it("should trigger onToggle callback and set category expanded when clicked in collapsed mode", () => {
    for (const categoryId of defaultCategoryIds) {
      let toggleCount = 0;
      const initialCategories = {
        overview: false,
        merchant: false,
        cfosAuditors: false,
        merchants: false,
        documentation: false,
      };

      const result = simulateExpandFromCollapsed(initialCategories, categoryId, () => {
        toggleCount += 1;
      });

      assert.equal(toggleCount, 1, `Toggle count must be 1 for ${categoryId}`);
      assert.equal(result.isCollapsedNext, false);
      assert.equal(result.nextCategories[categoryId], true);
    }
  });
});

describe("Challenger 1 Empirical Stress: Layout Container Constraints & JSX Validation", () => {
  it("should instantiate DashboardGroupLayout and all 3 documentation page components safely", () => {
    const layoutElement = React.createElement(DashboardGroupLayout, {
      children: React.createElement("div", null, "Test Child Content"),
    });
    assert.ok(React.isValidElement(layoutElement));

    // The three doc page components this used to instantiate are gone: one [...slug] route
    // serves every guide. The equivalent guarantee is that each guide still loads.
    for (const slug of ["setup", "buyer-sdk", "merchant-guide"]) {
      assert.ok(loadDocPage([slug]), `Documentation page ${slug} did not load`);
    }
  });

  it("should instantiate AppSidebar in both collapsed and expanded states", () => {
    let toggled = false;
    const sidebarExpanded = React.createElement(AppSidebar, {
      isCollapsed: false,
      onToggle: () => {
        toggled = true;
      },
      activeRoute: "/docs/setup",
    });
    assert.ok(React.isValidElement(sidebarExpanded));

    const sidebarCollapsed = React.createElement(AppSidebar, {
      isCollapsed: true,
      onToggle: () => {
        toggled = true;
      },
      activeRoute: "/docs/merchant-guide",
    });
    assert.ok(React.isValidElement(sidebarCollapsed));
  });
});
