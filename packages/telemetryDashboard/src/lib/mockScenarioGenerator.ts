import {
  defaultBuyerAgentDid,
  defaultMerchantDid,
  defaultUserCfoDid,
} from "@/constants/dashboardConstants";
import { TelemetryEvent } from "@/types/telemetryEventTypes";

export function createNominalSettlementEvents(sessionId: string): ReadonlyArray<TelemetryEvent> {
  const now = Date.now();
  return [
    {
      eventId: `evt-pow-${now}`,
      eventType: "POW_CHALLENGE_SOLVED",
      timestampMs: now - 350,
      sessionId,
      payload: {
        challenge: "a9f8b7c6d5e4f3a2",
        nonce: 48921,
        hash: "0000a7b8c9d0e1f2",
        solveDurationMs: 14,
        leadingZeros: 4,
      },
    },
    {
      eventId: `evt-mcp-quote-${now}`,
      eventType: "MCP_TOOL_CALL",
      timestampMs: now - 300,
      sessionId,
      payload: {
        toolName: "get_live_sku_quote",
        callId: "call-quote-001",
        callerAgentId: defaultBuyerAgentDid,
        parameters: { sku_id: "SKU-001", quantity: 1, delivery_pincode: "560001" },
      },
    },
    {
      eventId: `evt-mcp-res-${now}`,
      eventType: "MCP_TOOL_RESULT",
      timestampMs: now - 260,
      sessionId,
      payload: {
        toolName: "get_live_sku_quote",
        callId: "call-quote-001",
        success: true,
        result: {
          base_unit_price_paise: 420000,
          offered_unit_price_paise: 420000,
          gst_rate_percent: 18,
          hsn_code: "8504",
        },
        durationMs: 40,
      },
    },
    {
      eventId: `evt-inv-lock-${now}`,
      eventType: "INVENTORY_LOCKED",
      timestampMs: now - 220,
      sessionId,
      payload: {
        skuId: "SKU-001",
        quantityLocked: 1,
        lockToken: "lock-f782-990a-11bc",
        fencingToken: 1042,
        ttlSeconds: 60,
      },
    },
    {
      eventId: `evt-mandate-intent-${now}`,
      eventType: "MANDATE_SIGNED",
      timestampMs: now - 180,
      sessionId,
      payload: {
        mandateType: "INTENT",
        mandateHash: "0x89ab45cd67ef123489ab45cd67ef123489ab45cd67ef123489ab45cd67ef1234",
        signerKeyDid: defaultUserCfoDid,
        signatureHex: "ed25519_sig_intent_9876543210abcdef9876543210abcdef",
        maxBudgetPaise: 500000,
        verificationStatus: "VALID",
        canonicalJcsPreview: '{"budgetPaise":500000,"category":"industrial_electronics"}',
      },
    },
    {
      eventId: `evt-mandate-exec-${now}`,
      eventType: "MANDATE_SIGNED",
      timestampMs: now - 120,
      sessionId,
      payload: {
        mandateType: "EXECUTION",
        mandateHash: "0x77bb88cc99dd00ee11ff22aa33bb44cc55dd66ee77ff88aa99bb00cc11dd22ee",
        signerKeyDid: defaultBuyerAgentDid,
        signatureHex: "ed25519_sig_exec_1234567890abcdef1234567890abcdef",
        boundChainHash: "0x89ab45cd67ef123489ab45cd67ef123489ab45cd67ef123489ab45cd67ef1234",
        totalAmountPaise: 420000,
        verificationStatus: "VALID",
        canonicalJcsPreview: '{"boundChainHash":"0x89ab...","totalAmountPaise":420000}',
      },
    },
    {
      eventId: `evt-pay-captured-${now}`,
      eventType: "PAYMENT_CAPTURED",
      timestampMs: now - 40,
      sessionId,
      payload: {
        paymentId: "pay_A2A_Live_982341",
        orderId: "order_Mesh_881290",
        amountPaise: 420000,
        currency: "INR",
        status: "captured",
        transfers: [
          {
            transferId: "trf_merchant_001",
            recipientAccountId: "acc_merchant_nexus_01",
            amountPaise: 380000,
            feePaise: 0,
          },
          {
            transferId: "trf_platform_002",
            recipientAccountId: "acc_razoragent_protocol",
            amountPaise: 2000,
            feePaise: 0,
          },
          {
            transferId: "trf_logistics_003",
            recipientAccountId: "acc_delhivery_direct",
            amountPaise: 38000,
            feePaise: 0,
          },
        ],
        gstrInvoiceHash: "0xfa9812bc67de45fe9812bc67de45fe9812bc67de45fe",
        cgstPaise: 32034,
        sgstPaise: 32034,
      },
    },
  ];
}

export function createNegotiationScenarioEvents(sessionId: string): ReadonlyArray<TelemetryEvent> {
  const now = Date.now();
  return [
    {
      eventId: `evt-bid-turn-1-${now}`,
      eventType: "BID_TURN_COMPLETED",
      timestampMs: now - 300,
      sessionId,
      payload: {
        turnNumber: 1,
        maxTurns: 5,
        buyerBidPaise: 330000,
        sellerAskPaise: 360000,
        spreadPaise: 30000,
        microFeePaidPaise: 50,
        cumulativeMicroFeesPaise: 50,
        status: "IN_PROGRESS",
      },
    },
    {
      eventId: `evt-bid-turn-2-${now}`,
      eventType: "BID_TURN_COMPLETED",
      timestampMs: now - 200,
      sessionId,
      payload: {
        turnNumber: 2,
        maxTurns: 5,
        buyerBidPaise: 332500,
        sellerAskPaise: 345000,
        spreadPaise: 12500,
        microFeePaidPaise: 50,
        cumulativeMicroFeesPaise: 100,
        status: "IN_PROGRESS",
      },
    },
    {
      eventId: `evt-bid-turn-3-${now}`,
      eventType: "BID_TURN_COMPLETED",
      timestampMs: now - 100,
      sessionId,
      payload: {
        turnNumber: 3,
        maxTurns: 5,
        buyerBidPaise: 335000,
        sellerAskPaise: 335000,
        spreadPaise: 0,
        microFeePaidPaise: 50,
        cumulativeMicroFeesPaise: 150,
        status: "CONVERGED",
      },
    },
    {
      eventId: `evt-neg-conv-${now}`,
      eventType: "NEGOTIATION_CONVERGED",
      timestampMs: now - 50,
      sessionId,
      payload: {
        finalAgreedUnitPricePaise: 335000,
        totalTurns: 3,
        totalGrossPaise: 19765000,
        contractAstHash: "0xcc99aa1188bb33dd44ee55ff66aa77bb88cc99dd00ee11ff",
      },
    },
  ];
}

export function createOosHealingScenarioEvents(sessionId: string): ReadonlyArray<TelemetryEvent> {
  const now = Date.now();
  return [
    {
      eventId: `evt-oos-heal-${now}`,
      eventType: "OOS_HEALED",
      timestampMs: now - 80,
      sessionId,
      payload: {
        originalSkuId: "SKU-101",
        substituteSkuId: "SKU-104",
        cosineSimilarity: 0.924,
        originalPricePaise: 420000,
        substitutePricePaise: 425000,
        priceDeltaPaise: 5000,
        healingDurationMs: 214,
        patchedMandateHash: "0x12fe89ab34cd56ef78ab90cd12ef34ab56cd78ef",
        negativeConstraintsPassed: true,
      },
    },
  ];
}
