// How a live telemetry event is presented on /playground/live-agent.
//
// The Layer Explorer renders runs the dashboard itself drove, so its driver could stamp every
// step with a layer, a package and a narrative. Events arriving from an EXTERNAL agent carry no
// such stamps -- only an eventType, a sessionId and a payload -- so the mapping has to live
// here instead.
//
// Nothing in this file asserts that a step ran. It only describes events that actually arrived:
// a tool the mesh does not publish simply never appears.

import type { TelemetryEventType } from "@/types/telemetryEventTypes";

export const liveAgentPageTitle = "Live Agent Session";
export const liveAgentPageDescription =
  "Tool calls from an external agent -- Claude Desktop, Claude Code, Cursor -- grouped into one " +
  "session as they arrive. Nothing here is scripted: every stage is here because the agent " +
  "really made that call -- what you are reading is this tab's own record of the run.";

export const noSessionsHeading = "No agent sessions yet";
export const noSessionsBody =
  "Connect your agent to http://localhost:4001/mcp and ask it to find something. Each MCP tool " +
  "call publishes to the telemetry stream and appears here, grouped by the agent's session.";
export const noSelectionHeading = "Nothing to inspect yet";
export const noSelectionBody =
  "Select any stage to see the tool arguments and the result the mesh returned.";

export const sessionLabelPrefix = "Session";
export const sessionIdDisplayLength = 8;
export const liveAgentStepIdPrefix = "live";

/** A stdio MCP server has one session per process, so its id carries this prefix instead of a UUID. */
export const stdioSessionPrefix = "stdio";

export interface LiveEventPresentation {
  readonly title: string;
  readonly narrative: string;
  readonly protocolLayer: string;
  readonly implementedBy: string;
}

const mcpToolsPath = "packages/mcpServer/src/tools";
const mandateBuilderPath = "packages/buyerSdkTs/src/agentMandateBuilder.ts";
const mandateEnginePath = "packages/mandateEngine";
const vectorHealerPath = "packages/vectorHealer";
const x402Path = "packages/x402Gateway/src";

const discoveryLayer = "Discovery";
const negotiationLayer = "Negotiation";
const resilienceLayer = "Resilience";
const settlementLayer = "Settlement";
const ingressLayer = "Ingress Shield";

/** Per-tool presentation for MCP_TOOL_CALL / MCP_TOOL_RESULT pairs, keyed by tool name. */
export const toolPresentation: Readonly<Record<string, LiveEventPresentation>> = {
  search_catalog: {
    title: "Discover products",
    narrative:
      "The agent described what it wanted in plain language and the mesh ranked the catalog by " +
      "semantic similarity. Check embedding_mode in the result: 'hash' means the ranking is not " +
      "semantic and its order carries no meaning.",
    protocolLayer: discoveryLayer,
    implementedBy: mcpToolsPath
  },
  get_live_sku_quote: {
    title: "Quote a SKU",
    narrative:
      "Live unit price, the auto-discount stack and exact statutory GST, sealed with an HMAC " +
      "quote hash so a later stage can prove the price came from this mesh.",
    protocolLayer: discoveryLayer,
    implementedBy: mcpToolsPath
  },
  reserve_inventory_lock: {
    title: "Reserve stock",
    narrative:
      "An atomic Redis reservation with a monotonic fencing token, so two agents cannot sell the " +
      "same unit twice.",
    protocolLayer: discoveryLayer,
    implementedBy: mcpToolsPath
  },
  verify_shipping_sla: {
    title: "Check serviceability",
    narrative: "Zonal courier SLA and weight surcharge for the delivery pincode.",
    protocolLayer: discoveryLayer,
    implementedBy: mcpToolsPath
  },
  establish_agent_delegation: {
    title: "Delegate a budget",
    narrative:
      "The agent proved possession of its key, or asked the mesh to hold one, and received a " +
      "signed Intent Mandate bounding what it may spend. key_custody in the result says which " +
      "party holds buyer authority.",
    protocolLayer: settlementLayer,
    implementedBy: mandateBuilderPath
  },
  create_cart_mandate: {
    title: "Sign the cart",
    narrative:
      "The mesh re-derived every price from its own engines and compared them against the " +
      "agent's quote hash before the merchant key signed, so the signature attests only to " +
      "numbers the merchant produced.",
    protocolLayer: settlementLayer,
    implementedBy: mandateBuilderPath
  },
  sign_execution_mandate: {
    title: "Bind intent to cart",
    narrative:
      "An Execution Mandate hash-linking the Intent and Cart mandates. Under agent_held custody " +
      "the mesh returns bytes and no signature; under custodial mode it signs with the session key.",
    protocolLayer: settlementLayer,
    implementedBy: mandateBuilderPath
  },
  browse_catalog: {
    title: "Browse the catalog",
    narrative:
      "Enumerates the SKUs the mesh can actually quote, so an agent can see the whole catalog " +
      "rather than only what a semantic query happened to rank.",
    protocolLayer: discoveryLayer,
    implementedBy: mcpToolsPath
  },
  negotiate_price: {
    title: "Negotiate the price",
    narrative:
      "An alternating-offer x402-INR negotiation against the merchant's own policy. The floor is " +
      "the merchant's, never the buyer's: an agent cannot name a price the policy did not allow.",
    protocolLayer: negotiationLayer,
    implementedBy: x402Path
  },
  execute_settlement: {
    title: "Settle",
    narrative:
      "The 2PC settlement saga: signature chain, budget gate, arithmetic enclave, nonce ledger, " +
      "then capture, Route split and the GSTR-1 invoice.",
    protocolLayer: settlementLayer,
    implementedBy: mandateEnginePath
  }
};

export const unknownToolPresentation: LiveEventPresentation = {
  title: "MCP tool call",
  narrative: "A tool this view has no description for. The arguments and result are shown as sent.",
  protocolLayer: discoveryLayer,
  implementedBy: mcpToolsPath
};

/** Presentation for non-tool events that belong to the same agent session. */
export const eventPresentation: Partial<
  Readonly<Record<TelemetryEventType, LiveEventPresentation>>
> = {
  INVENTORY_LOCKED: {
    title: "Stock reserved",
    narrative: "The reservation the lock tool took, with its TTL.",
    protocolLayer: discoveryLayer,
    implementedBy: mcpToolsPath
  },
  MANDATE_SIGNED: {
    title: "Mandate signed",
    narrative: "An Ed25519 signature over the mandate's RFC 8785 canonical bytes.",
    protocolLayer: settlementLayer,
    implementedBy: mandateEnginePath
  },
  PAYMENT_CAPTURED: {
    title: "Mesh settlement recorded",
    // Named for what actually happened. The engine's 2PC completed and the Route legs were
    // computed on the mesh's own ledger, but nothing has been charged: the Razorpay order is
    // created with amount_paid 0 until a person authorises it on the Settle screen. The old
    // "Payment captured" sat directly above the handoff card that asks the human to pay, and
    // claimed a capture the API record contradicts.
    narrative:
      "Two-phase commit completed and the Route split was computed on the mesh's own ledger. " +
      "The Razorpay order is open but unpaid -- a person still has to authorise the charge.",
    protocolLayer: settlementLayer,
    implementedBy: mandateEnginePath
  },
  BUDGET_BLOCKED: {
    title: "Budget gate refused",
    narrative:
      "The mesh refused to settle. This is the protocol working: the delegation's bounds held.",
    protocolLayer: settlementLayer,
    implementedBy: mandateEnginePath
  },
  ROUTE_ROLLBACK_TRIGGERED: {
    title: "Split rolled back",
    narrative: "A transfer leg failed, so the saga compensated rather than leaving a partial split.",
    protocolLayer: settlementLayer,
    implementedBy: mandateEnginePath
  },
  OOS_HEALED: {
    title: "Cart healed",
    narrative: "An out-of-stock line was replaced with the nearest vector match.",
    protocolLayer: resilienceLayer,
    implementedBy: vectorHealerPath
  },
  POW_CHALLENGE_SOLVED: {
    title: "Proof of work solved",
    narrative: "The agent paid the Sybil shield's compute cost before being served.",
    protocolLayer: ingressLayer,
    implementedBy: x402Path
  },
  BID_TURN_COMPLETED: {
    title: "Negotiation turn",
    narrative: "One turn of Rubinstein-Stahl bilateral bargaining.",
    protocolLayer: negotiationLayer,
    implementedBy: x402Path
  },
  NEGOTIATION_CONVERGED: {
    title: "Negotiation settled",
    narrative: "Both sides converged on a price.",
    protocolLayer: negotiationLayer,
    implementedBy: x402Path
  }
};

// Which HTTP status on a failed tool call means "the mesh refused" rather than "the mesh broke".
//
// This distinction is the whole point of the REFUSED state: a refusal is the protocol working
// and is rendered in accent, while FAILED is red. Colouring a 500 as REFUSED would tell a
// reader the mesh successfully defended itself when in fact a service fell over -- the exact
// misrepresentation stepStatusPresentation warns against.
//
// 502 belongs here because the settlement saga returns it after compensating a failed transfer
// leg: the rollback is the saga doing its job, not an unhandled fault.
export const protocolRefusalStatusCodes: readonly number[] = [400, 402, 403, 409, 422, 502];

export const serverErrorFloor = 500;

/** HEARTBEAT carries no protocol work, so it never becomes a step. */
export const ignoredEventTypes: readonly TelemetryEventType[] = ["HEARTBEAT"];
