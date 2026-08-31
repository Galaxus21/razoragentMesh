// The canonical six-layer mesh stack, L0 through L5. Everything else defers to this file.
//
// The repository used to carry four numberings at once: README.md said "4-layer" in prose while
// drawing six rows, PROJECT.md numbered by package, this map defined five, and the protocol
// driver labelled the mandate chain "Layer 2" where the map calls it Layer 4. Picking a winner
// was the only way out, and this is it -- chosen because it is the only machine-readable scheme,
// it already drives /protocol, and `implementedBy` ties every layer to the packages that build
// it, so the rest of the repo can be checked against it rather than hand-maintained.
//
// protocolLayerLabels.test.ts asserts that the layer strings baked into the driver and the UI
// still agree with the ordinals here, so the numberings cannot silently diverge again.

import { scenarioHappyPath, scenarioTamperedMandate } from "./scenarioCatalog";
import type { MeshServiceId } from "./meshServiceRegistry";
import type { TelemetryEventType } from "@/types/telemetryEventTypes";

export interface ProtocolLayerNode {
  readonly layerId: string;
  readonly ordinal: number;
  readonly title: string;
  readonly tagline: string;
  readonly responsibilities: readonly string[];
  readonly eventsEmitted: readonly TelemetryEventType[];
  readonly implementedBy: readonly string[];
  // Empty for a layer with no long-running service of its own: the telemetry layer is the
  // dashboard you are already looking at, and the healer runs inside the merchant API.
  readonly serviceIds: readonly MeshServiceId[];
  readonly docRoute: string;
  readonly scenarioId: string;
  readonly scenarioHint: string;
}

export const protocolLayerNodes: readonly ProtocolLayerNode[] = [
  {
    layerId: "ingress",
    ordinal: 0,
    title: "Ingress Shield",
    tagline: "Everything untrusted is scrubbed or priced before it reaches the protocol.",
    responsibilities: [
      "Strips zero-width, ANSI and markdown injection out of merchant-supplied catalog text",
      "Prices anti-spam into the protocol with a proof-of-work challenge on HTTP 402",
      "Rejects Sybil traffic at the edge rather than inside the negotiation state machine",
    ],
    eventsEmitted: ["POW_CHALLENGE_SOLVED"],
    implementedBy: [
      "packages/catalogSanitizer",
      "packages/x402Gateway/src/middleware/proofOfWorkMiddleware.py",
    ],
    serviceIds: ["x402Gateway"],
    docRoute: "/docs/setup",
    scenarioId: scenarioHappyPath,
    scenarioHint: "Every metered call in a run clears a proof-of-work challenge first.",
  },
  {
    layerId: "discovery",
    ordinal: 1,
    title: "Discovery",
    tagline: "Model Context Protocol tools an agent can call before it commits to anything.",
    responsibilities: [
      "Serves live SKU pricing with the HSN code and GST rate the cart mandate will need",
      "Verifies a shipping SLA for a pincode and parcel weight",
      "Reserves a fenced, TTL-bounded inventory lock and returns its token",
    ],
    eventsEmitted: ["MCP_TOOL_CALL", "MCP_TOOL_RESULT", "INVENTORY_LOCKED"],
    implementedBy: ["packages/mcpServer/src/tools", "packages/mcpServer/src/http"],
    serviceIds: ["mcpServer", "merchantApi"],
    docRoute: "/docs/buyer-sdk",
    scenarioId: scenarioHappyPath,
    scenarioHint: "Runs all three discovery tools against the live catalog.",
  },
  {
    layerId: "negotiation",
    ordinal: 2,
    title: "Negotiation",
    tagline: "HTTP 402 micro-metering and bilateral bargaining over price.",
    responsibilities: [
      "Issues a proof-of-work challenge on HTTP 402 to price anti-spam into the protocol",
      "Escrows micro-fees per bargaining turn",
      "Runs the Rubinstein-Stahl concession state machine to convergence",
    ],
    eventsEmitted: ["BID_TURN_COMPLETED", "NEGOTIATION_CONVERGED"],
    implementedBy: ["packages/x402Gateway/src"],
    serviceIds: ["x402Gateway"],
    docRoute: "/negotiation-hub",
    scenarioId: scenarioHappyPath,
    scenarioHint:
      "The happy path solves a proof-of-work challenge transparently inside reserveInventoryLock.",
  },
  {
    layerId: "resilience",
    ordinal: 3,
    title: "Resilience",
    tagline: "Vector substitution when the chosen SKU cannot be fulfilled.",
    responsibilities: [
      "Finds the nearest in-stock substitute by cosine similarity over Qdrant",
      "Applies negative constraints so a substitute cannot violate the buyer's stated exclusions",
      "Patches the cart mandate and re-signs it rather than silently swapping the line item",
    ],
    eventsEmitted: ["OOS_HEALED"],
    implementedBy: ["packages/vectorHealer"],
    serviceIds: ["merchantApi"],
    docRoute: "/self-healing",
    scenarioId: scenarioHappyPath,
    scenarioHint: "Healing only triggers on an out-of-stock SKU, which the happy path avoids.",
  },
  {
    layerId: "settlement",
    ordinal: 4,
    title: "Settlement",
    tagline: "AP2 mandate chain, statutory tax, and a two-phase commit over Razorpay Route.",
    responsibilities: [
      "Verifies the Intent -> Cart -> Execution hash chain and all three Ed25519 signatures",
      "Recomputes the GST split in an arithmetic enclave instead of trusting the cart",
      "Runs the 2PC saga and compensates every transfer if any leg fails",
    ],
    eventsEmitted: ["MANDATE_SIGNED", "PAYMENT_CAPTURED", "BUDGET_BLOCKED", "ROUTE_ROLLBACK_TRIGGERED"],
    implementedBy: ["packages/mandateEngine", "packages/buyerSdkTs/src/agentMandateBuilder.ts"],
    serviceIds: ["mandateEngine"],
    docRoute: "/security-audit",
    scenarioId: scenarioTamperedMandate,
    scenarioHint: "Tampers with a signed cart mandate and watches the chain verification refuse it.",
  },
  {
    layerId: "telemetry",
    ordinal: 5,
    title: "Telemetry",
    tagline: "The SSE bus and this dashboard.",
    responsibilities: [
      "Broadcasts every protocol event to subscribers over Server-Sent Events",
      "Stamps each event with its provenance so a fixture replay cannot be shown as a live run",
      "Drives the playground, the adversarial grid and the SDK console from real traffic",
    ],
    eventsEmitted: ["HEARTBEAT"],
    implementedBy: [
      "packages/mandateEngine/telemetryEmitter.py",
      "packages/telemetryDashboard/src",
    ],
    serviceIds: ["mandateEngine"],
    docRoute: "/docs/telemetry",
    scenarioId: scenarioHappyPath,
    scenarioHint: "Every step of a run is mirrored onto the bus as it completes.",
  },
];
