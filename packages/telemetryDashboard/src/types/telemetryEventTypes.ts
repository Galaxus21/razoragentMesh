export type TelemetryEventType =
  | "MCP_TOOL_CALL"
  | "MCP_TOOL_RESULT"
  | "BID_TURN_COMPLETED"
  | "NEGOTIATION_CONVERGED"
  | "MANDATE_SIGNED"
  | "PAYMENT_CAPTURED"
  | "OOS_HEALED"
  | "BUDGET_BLOCKED"
  | "POW_CHALLENGE_SOLVED"
  | "INVENTORY_LOCKED"
  | "ROUTE_ROLLBACK_TRIGGERED"
  | "HEARTBEAT";

export type SseConnectionState = "CONNECTING" | "CONNECTED" | "DISCONNECTED" | "ERROR";

// Whether an event describes work that actually happened. Stamped by the publisher; see
// packages/mandateEngine/telemetryEmitter.py. Absent on events from a publisher that predates
// the field, which is why the resolver treats undefined as UNKNOWN rather than as LIVE.
export type TelemetryProvenance = "LIVE" | "SYNTHETIC" | "UNKNOWN";

// What the connection badge is allowed to claim. SseConnectionState describes the socket;
// this describes the events travelling over it. An open socket carrying scripted fixtures is
// CONNECTED but it is not LIVE, and the badge used to conflate the two.
export type TelemetryStreamMode =
  | "LIVE"
  | "REPLAY"
  | "MIXED"
  | "IDLE"
  | "CONNECTING"
  | "OFFLINE";

export type MandateKind = "INTENT" | "CART" | "EXECUTION" | "AMENDMENT";

export interface BaseTelemetryEvent<TType extends TelemetryEventType, TPayload> {
  readonly eventId: string;
  readonly eventType: TType;
  readonly timestampMs: number;
  readonly sessionId: string;
  readonly payload: TPayload;
  readonly provenance?: TelemetryProvenance;
}

export interface McpToolCallPayload {
  readonly toolName: "get_live_sku_quote" | "reserve_inventory_lock" | "verify_shipping_sla" | string;
  readonly callId: string;
  readonly callerAgentId: string;
  readonly parameters: Record<string, unknown>;
}

export interface McpToolResultPayload {
  readonly toolName: string;
  readonly callId: string;
  readonly success: boolean;
  readonly result: Record<string, unknown>;
  readonly durationMs: number;
}

export interface BidTurnCompletedPayload {
  readonly turnNumber: number;
  readonly maxTurns: number;
  readonly buyerBidPaise: number;
  readonly sellerAskPaise: number;
  readonly spreadPaise: number;
  readonly microFeePaidPaise: number;
  readonly cumulativeMicroFeesPaise: number;
  readonly status: "IN_PROGRESS" | "CONVERGED" | "EXHAUSTED";
}

export interface NegotiationConvergedPayload {
  readonly finalAgreedUnitPricePaise: number;
  readonly totalTurns: number;
  readonly totalGrossPaise: number;
  readonly contractAstHash: string;
}

export interface MandateSignedPayload {
  readonly mandateType: MandateKind;
  readonly mandateHash: string;
  readonly signerKeyDid: string;
  readonly signatureHex: string;
  readonly boundChainHash?: string;
  readonly totalAmountPaise?: number;
  readonly maxBudgetPaise?: number;
  readonly canonicalJcsPreview?: string;
  readonly verificationStatus?: "VALID" | "INVALID";
}

export interface RouteTransferItem {
  readonly transferId: string;
  readonly recipientAccountId: string;
  readonly amountPaise: number;
  readonly feePaise: number;
}

export interface PaymentCapturedPayload {
  readonly paymentId: string;
  readonly orderId: string;
  readonly amountPaise: number;
  readonly currency: "INR";
  readonly status: "captured";
  readonly transfers: ReadonlyArray<RouteTransferItem>;
  readonly gstrInvoiceHash: string;
  readonly cgstPaise?: number;
  readonly sgstPaise?: number;
  readonly igstPaise?: number;
}

export interface OosHealedPayload {
  readonly originalSkuId: string;
  readonly substituteSkuId: string;
  readonly cosineSimilarity: number;
  readonly originalPricePaise: number;
  readonly substitutePricePaise: number;
  readonly priceDeltaPaise: number;
  readonly healingDurationMs: number;
  readonly patchedMandateHash: string;
  readonly negativeConstraintsPassed?: boolean;
}

export interface BudgetBlockedPayload {
  readonly intentBudgetPaise: number;
  readonly attemptedAmountPaise: number;
  readonly deltaPaise: number;
  readonly blockedReason: string;
  readonly razorpayCallsCount: 0;
}

export interface PowChallengeSolvedPayload {
  readonly challenge: string;
  readonly nonce: number;
  readonly hash: string;
  readonly solveDurationMs: number;
  readonly leadingZeros: number;
}

export interface InventoryLockedPayload {
  readonly skuId: string;
  readonly quantityLocked: number;
  readonly lockToken: string;
  readonly fencingToken: number;
  readonly ttlSeconds: number;
}

export interface RouteRollbackTriggeredPayload {
  readonly transferId: string;
  readonly failureReason: string;
  readonly compensationAction: "reverse_transfer";
  readonly rollbackStatus: "COMPLETED" | "FAILED";
}

export interface HeartbeatPayload {
  readonly serverTimestampMs: number;
  readonly activeSessionsCount: number;
}

export type TelemetryEvent =
  | BaseTelemetryEvent<"MCP_TOOL_CALL", McpToolCallPayload>
  | BaseTelemetryEvent<"MCP_TOOL_RESULT", McpToolResultPayload>
  | BaseTelemetryEvent<"BID_TURN_COMPLETED", BidTurnCompletedPayload>
  | BaseTelemetryEvent<"NEGOTIATION_CONVERGED", NegotiationConvergedPayload>
  | BaseTelemetryEvent<"MANDATE_SIGNED", MandateSignedPayload>
  | BaseTelemetryEvent<"PAYMENT_CAPTURED", PaymentCapturedPayload>
  | BaseTelemetryEvent<"OOS_HEALED", OosHealedPayload>
  | BaseTelemetryEvent<"BUDGET_BLOCKED", BudgetBlockedPayload>
  | BaseTelemetryEvent<"POW_CHALLENGE_SOLVED", PowChallengeSolvedPayload>
  | BaseTelemetryEvent<"INVENTORY_LOCKED", InventoryLockedPayload>
  | BaseTelemetryEvent<"ROUTE_ROLLBACK_TRIGGERED", RouteRollbackTriggeredPayload>
  | BaseTelemetryEvent<"HEARTBEAT", HeartbeatPayload>;
