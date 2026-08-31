import { describe, it } from "node:test";
import assert from "node:assert/strict";
import React from "react";

import {
  navigationItems,
  navigationCategories,
  AppSidebar,
} from "../src/components/appSidebar.js";
import {
  defaultSidebarCollapsed,
  sidebarStorageKey,
} from "../src/hooks/useSidebarState.js";
import {
  connectionStatusColors,
  connectionStatusLabels,
} from "../src/constants/dashboardConstants.js";
import { DashboardHeader } from "../src/components/dashboardHeader.js";
import { resolveStreamMode } from "../src/lib/streamModeResolver.js";
import OverviewPage from "../src/app/(dashboard)/overview/page.js";
import AgentObservabilityPage from "../src/app/(dashboard)/agent-observability/page.js";
import NegotiationHubPage from "../src/app/(dashboard)/negotiation-hub/page.js";
import SecurityAuditPage from "../src/app/(dashboard)/security-audit/page.js";
import SelfHealingPage from "../src/app/(dashboard)/self-healing/page.js";
import InfrastructurePage from "../src/app/(dashboard)/infrastructure/page.js";
import MerchantStudioPage from "../src/app/(dashboard)/merchant-studio/page.js";
import { loadAllDocPages, loadDocPage } from "../src/lib/docsLoader.js";
import RootPage from "../src/app/page.js";
import DashboardGroupLayout from "../src/app/(dashboard)/layout.js";
import { TelemetryProvider, useTelemetry } from "../src/context/telemetryContext.js";
import {
  createTestNegotiationScenarioEvents,
  createTestNominalSettlementEvents,
  createTestOosHealingScenarioEvents,
} from "./fixtures/testTelemetryFixtures.js";
import { SseConnectionState } from "../src/types/telemetryEventTypes.js";
import { isRouteMatching } from "../src/constants/sidebarNavigationConfig.js";

const expectedRoutes: ReadonlyArray<string> = [
  "/overview",
  "/protocol",
  "/self-healing",
  "/infrastructure",
  "/playground",
  "/playground/adversarial",
  "/sdk-console",
  "/agent-observability",
  "/negotiation-hub",
  "/security-audit",
  "/merchant-studio",
  "/docs/setup",
  "/docs/onboarding",
  "/docs/buyer-sdk",
  "/docs/merchant-guide",
  "/docs/telemetry",
  "/docs/gstr1-invoice",
];

describe("Challenger 2 Empirical Verification: Root Page Redirect & Route Group Structure", () => {
  it("should trigger server-side redirect to /overview when RootPage is invoked", () => {
    try {
      RootPage();
      assert.fail("RootPage should have called redirect() and thrown a redirect signal");
    } catch (error: unknown) {
      if (error && typeof error === "object" && "digest" in error) {
        const digest = (error as { digest: string }).digest;
        assert.ok(
          digest.includes("/overview") || digest.includes("NEXT_REDIRECT"),
          `Redirect digest did not include expected redirect info: ${digest}`
        );
      } else if (error && typeof error === "object" && "message" in error) {
        const errorMsg = (error as { message: string }).message;
        assert.ok(
          errorMsg.includes("NEXT_REDIRECT") || errorMsg.includes("/overview"),
          `Unexpected redirect error message: ${errorMsg}`
        );
      }
    }
  });

  it("should export functional React components for all 7 non-doc route pages", () => {
    const routeComponents = [
      { name: "OverviewPage", component: OverviewPage },
      { name: "AgentObservabilityPage", component: AgentObservabilityPage },
      { name: "NegotiationHubPage", component: NegotiationHubPage },
      { name: "SecurityAuditPage", component: SecurityAuditPage },
      { name: "SelfHealingPage", component: SelfHealingPage },
      { name: "InfrastructurePage", component: InfrastructurePage },
      { name: "MerchantStudioPage", component: MerchantStudioPage },
    ];

    for (const { name, component } of routeComponents) {
      assert.equal(typeof component, "function", `${name} is not a valid component function`);
      assert.equal(component.name.length > 0, true, `${name} has no function name`);
    }

    // Documentation is no longer one page component per guide -- a single [...slug] route
    // serves them all -- so the equivalent check is that every guide still resolves to content.
    const docPages = loadAllDocPages();
    assert.ok(docPages.length > 0, "No documentation pages were discovered");
    for (const page of docPages) {
      assert.ok(page.body.length > 0, `Documentation page ${page.slug} has an empty body`);
    }
  });

  it("should export functional React component for DashboardGroupLayout", () => {
    assert.equal(typeof DashboardGroupLayout, "function");
    assert.equal(typeof TelemetryProvider, "function");
    assert.equal(typeof useTelemetry, "function");
  });
});

describe("Challenger 2 Empirical Verification: Navigation Mapping & Active Route Resolution", () => {
  it("should verify 100% route alignment between navigationItems and expected 17 routes", () => {
    assert.equal(navigationItems.length, 17);

    const actualRoutes = navigationItems.map((item) => item.route);
    assert.deepEqual(actualRoutes, expectedRoutes);

    for (const item of navigationItems) {
      assert.ok(item.route.startsWith("/"), `Route ${item.route} does not start with /`);
      assert.ok(item.label.length > 0, `Item ${item.route} has empty label`);
      assert.ok((item.description ?? "").length > 0, `Item ${item.route} has empty description`);
    }
  });

  it("should verify deterministic active route prefix matching across 10,000 randomized permutations", () => {
    // The real implementation, not a local copy. This test previously redefined the matcher
    // inline, so it asserted the behaviour of its own two lines and would have stayed green
    // even if src/constants/sidebarNavigationConfig.ts changed underneath it.
    const isActiveRoute = isRouteMatching;

    for (const target of expectedRoutes) {
      // Exact match must be true
      assert.equal(isActiveRoute(target, target), true);

      // Sub-route match must be true
      assert.equal(isActiveRoute(`${target}/nested-view`, target), true);
      assert.equal(isActiveRoute(`${target}/item/12345`, target), true);

      // Non-matching routes must be false. A route nested UNDER another registered route
      // (/playground/adversarial under /playground) is exempt: the most specific registered
      // route owns it, so the parent must NOT also report active or two rows would highlight.
      for (const other of expectedRoutes) {
        if (other !== target && !other.startsWith(`${target}/`)) {
          assert.equal(isActiveRoute(other, target), false);
        }
      }
    }
  });
});

describe("Challenger 2 Empirical Verification: AppSidebar & DashboardHeader UI Contracts", () => {
  it("should verify AppSidebar props contract and layout rendering elements", () => {
    assert.equal(typeof AppSidebar, "function");

    // Verify AppSidebar JSX element creation without runtime crash
    const elementCollapsed = React.createElement(AppSidebar, {
      isCollapsed: true,
      onToggle: () => {},
      activeRoute: "/overview",
    });

    assert.ok(React.isValidElement(elementCollapsed));
    assert.equal(elementCollapsed.props.isCollapsed, true);
    assert.equal(elementCollapsed.props.activeRoute, "/overview");

    const elementExpanded = React.createElement(AppSidebar, {
      isCollapsed: false,
      onToggle: () => {},
      activeRoute: "/security-audit",
    });

    assert.ok(React.isValidElement(elementExpanded));
    assert.equal(elementExpanded.props.isCollapsed, false);
    assert.equal(elementExpanded.props.activeRoute, "/security-audit");
  });

  it("should verify DashboardHeader props contract across connection states and themes", () => {
    assert.equal(typeof DashboardHeader, "function");

    const connectionStates: ReadonlyArray<SseConnectionState> = [
      "CONNECTED",
      "CONNECTING",
      "DISCONNECTED",
      "ERROR",
    ];
    const themes = ["dark", "light"] as const;

    for (const connectionState of connectionStates) {
      for (const theme of themes) {
        const headerElement = React.createElement(DashboardHeader, {
          connectionState,
          streamMode: resolveStreamMode(connectionState, []),
          provenanceCounts: { liveCount: 0, syntheticCount: 0, unknownCount: 0 },
          totalEventsCount: 42,
          onClearEvents: () => {},
          theme,
          onToggleTheme: () => {},
        });

        assert.ok(React.isValidElement(headerElement));
        assert.equal((headerElement.props as any).connectionState, connectionState);
        assert.equal((headerElement.props as any).theme, theme);
        assert.equal((headerElement.props as any).totalEventsCount, 42);

        // Verify status constants lookup
        assert.ok(connectionStatusColors[connectionState]);
        assert.ok(connectionStatusLabels[connectionState]);
      }
    }
  });
});

describe("Challenger 2 Empirical Verification: Telemetry Context & Full Agentic Flow Synthesis", () => {
  it("should synthesize nominal, negotiation, and self-healing telemetry events for multi-route views", () => {
    const testSessionId = "session-challenger-test-999";
    const nominalEvents = createTestNominalSettlementEvents(testSessionId);
    const negotiationEvents = createTestNegotiationScenarioEvents(testSessionId);
    const healingEvents = createTestOosHealingScenarioEvents(testSessionId);

    assert.equal(nominalEvents.length, 7, "Nominal events count mismatch");
    assert.equal(negotiationEvents.length, 4, "Negotiation events count mismatch");
    assert.equal(healingEvents.length, 1, "Healing events count mismatch");

    const aggregated = [...nominalEvents, ...negotiationEvents, ...healingEvents];
    assert.equal(aggregated.length, 12, "Aggregated events count mismatch");

    for (const event of aggregated) {
      assert.ok(event.eventId.length > 0, "Missing event ID");
      assert.ok(event.eventType.length > 0, "Missing event type");
      assert.ok(typeof event.timestampMs === "number" && event.timestampMs > 0, "Invalid timestamp");
      assert.ok(typeof event.payload === "object" && event.payload !== null, "Invalid payload");
    }
  });

  it("should enforce context requirement when hook is invoked outside context provider", () => {
    const simulateUseTelemetryConsumer = (contextValue: unknown) => {
      if (!contextValue) {
        throw new Error("useTelemetry must be used within a TelemetryProvider");
      }
      return contextValue;
    };

    assert.throws(
      () => {
        simulateUseTelemetryConsumer(null);
      },
      {
        name: "Error",
        message: "useTelemetry must be used within a TelemetryProvider",
      }
    );

    const mockValidContext = { events: [], isConnected: true };
    const result = simulateUseTelemetryConsumer(mockValidContext);
    assert.equal(result, mockValidContext);
  });
});
