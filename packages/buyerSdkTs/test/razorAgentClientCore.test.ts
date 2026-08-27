import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { AgentKeyManager } from "../src/agentKeyManager.js";
import {
  createSignedIntentMandate,
  createSignedCartMandate,
  createSignedExecutionMandate
} from "../src/agentMandateBuilder.js";
import { RazorAgentClient } from "../src/razorAgentClient.js";
import {
  headerBuyerAgentDid,
  headerPowChallenge,
  headerPowSolution
} from "../src/sdkConstants.js";
import type {
  CartMandate,
  IntentMandate,
  InventoryLockResponse,
  SettlementResult,
  SkuQuote,
  SlaVerificationResponse
} from "../src/types.js";

function createMockSkuQuote(skuId = "SKU-TEST-001"): SkuQuote {
  return {
    skuId,
    baseUnitPricePaise: 420000,
    finalUnitPricePaise: 400000,
    quantity: 1,
    taxableSubtotalPaise: 400000,
    taxBreakdown: { cgstPaise: 36000, sgstPaise: 36000, igstPaise: 0, totalTaxPaise: 72000 },
    appliedDiscounts: [{ code: "FESTIVE", name: "Festive ₹20 off", discountPaise: 2000 }],
    totalSavingsPaise: 2000,
    quoteExpiryTimestamp: 1700000060,
    quoteHash: "a".repeat(64),
    upcomingPromotions: []
  };
}

function createMockLockResponse(
  lockToken = "lock_uuid_12345",
  fencingToken = 42,
  skuId = "SKU-TEST-001"
): InventoryLockResponse {
  return {
    lockToken,
    fencingToken,
    skuId,
    quantityLocked: 1,
    expiresAtUnixMs: 1700000060000,
    lockSignature: "mock_signature_base64"
  };
}

function createMockSlaResponse(): SlaVerificationResponse {
  return {
    pincode: "560001",
    zone: "SOUTH_METRO",
    deliverySpeed: "EXPRESS",
    slaHours: 24,
    shippingFeePaise: 5000,
    weightGrams: 500
  };
}

function createTestIntentMandate(buyerDid: string, userKeyManager: AgentKeyManager, upiToken = "upi_circle_001"): IntentMandate {
  return createSignedIntentMandate(
    {
      delegatedAgentDid: buyerDid,
      maxBudgetPaise: 500000,
      singleTransactionLimitPaise: 500000,
      upiCircleDelegationToken: upiToken
    },
    userKeyManager
  );
}

function createTestCartMandate(
  merchantKeyManager: AgentKeyManager,
  skuId = "SKU-001",
  unitPricePaise = 420000,
  taxPaise = 75600,
  totalPaise = 495600,
  lockToken = "lock_tok_001"
): CartMandate {
  const halfTax = Math.floor(taxPaise / 2);
  return createSignedCartMandate(
    {
      merchantGstin: "29AABCU9603R1ZJ",
      merchantStateCode: "29",
      buyerDeliveryPincode: "560001",
      buyerDeliveryStateCode: "29",
      items: [{ skuId, quantity: 1, unitPricePaise, hsnCode: "8504", gstRatePercent: 18, lineTotalPaise: unitPricePaise }],
      taxableSubtotalPaise: unitPricePaise,
      taxBreakdown: { cgstPaise: halfTax, sgstPaise: halfTax, igstPaise: 0, totalTaxPaise: taxPaise },
      totalPaise,
      inventoryLockToken: lockToken,
      inventoryLockExpiresAt: 2000000000
    },
    merchantKeyManager
  );
}

function createMockSettlementResult(
  paymentId = "pay_live_001",
  amountPaise = 495600,
  taxableAmountPaise = 420000,
  totalTaxPaise = 75600,
  transfers: SettlementResult["transfers"] = []
): SettlementResult {
  const halfTax = Math.floor(totalTaxPaise / 2);
  return {
    status: "captured",
    paymentId,
    amountPaise,
    currency: "INR",
    transfers,
    invoice: {
      invoiceNumber: "INV-" + paymentId,
      merchantGstin: "29AABCU9603R1ZJ",
      buyerDeliveryStateCode: "29",
      taxableAmountPaise,
      totalCgstPaise: halfTax,
      totalSgstPaise: halfTax,
      totalIgstPaise: 0,
      grandTotalPaise: amountPaise,
      cryptographicAuditHash: "b".repeat(64)
    }
  };
}

describe("RazorAgentClientCore", () => {
  const userKeyManager = AgentKeyManager.generate();
  const merchantKeyManager = AgentKeyManager.generate();
  const buyerKeyManager = AgentKeyManager.generate();

  it("should initialize with default configuration and generated key manager", () => {
    const client = new RazorAgentClient({ buyerKeyManager });
    assert.equal(client.getAgentDid(), buyerKeyManager.getAgentDid());
    assert.equal(client.getBuyerKeyManager(), buyerKeyManager);
  });

  it("should discover live SKU quote via mock fetch", async () => {
    const mockQuote = createMockSkuQuote("SKU-TEST-001");
    const customFetch: typeof fetch = async (input) => {
      const urlStr = input.toString();
      assert.ok(urlStr.includes("skuId=SKU-TEST-001"));
      return new Response(JSON.stringify(mockQuote), { status: 200, headers: { "Content-Type": "application/json" } });
    };

    const client = new RazorAgentClient({ buyerKeyManager, customFetch });
    const quote = await client.getLiveSkuQuote("SKU-TEST-001", 1, { promoCode: "FESTIVE" });
    assert.equal(quote.skuId, "SKU-TEST-001");
    assert.equal(quote.finalUnitPricePaise, 400000);
    assert.equal(quote.totalSavingsPaise, 2000);
  });

  it("should reserve inventory lock directly when no 402 challenge is presented", async () => {
    const mockLock = createMockLockResponse("lock_uuid_12345", 42, "SKU-TEST-001");
    const customFetch: typeof fetch = async () =>
      new Response(JSON.stringify(mockLock), { status: 200, headers: { "Content-Type": "application/json" } });

    const client = new RazorAgentClient({ buyerKeyManager, customFetch });
    const lock = await client.reserveInventoryLock("SKU-TEST-001", 1);
    assert.equal(lock.lockToken, "lock_uuid_12345");
    assert.equal(lock.fencingToken, 42);
    assert.equal(lock.quantityLocked, 1);
  });

  it("should handle HTTP 402 PoW challenge and successfully retry with PoW solution", async () => {
    let callCount = 0;
    const challengeToken = "pow_challenge_tok_999";
    const mockLock = createMockLockResponse("lock_pow_solved_777", 101, "SKU-POW-001");

    const customFetch: typeof fetch = async (_input, init) => {
      callCount += 1;
      if (callCount === 1) {
        return new Response(
          JSON.stringify({
            statusCode: 402,
            wwwAuthenticate: 'x402-INR tokenCostPaise="50"',
            challengeToken,
            tokenCostPaise: 50,
            powDifficultyZeros: 3
          }),
          { status: 402, headers: { "Content-Type": "application/json" } }
        );
      }
      const headers = init?.headers as Record<string, string>;
      assert.equal(headers[headerPowChallenge], challengeToken);
      assert.ok(headers[headerPowSolution]);
      assert.equal(headers[headerBuyerAgentDid], buyerKeyManager.getAgentDid());
      return new Response(JSON.stringify(mockLock), { status: 200, headers: { "Content-Type": "application/json" } });
    };

    const client = new RazorAgentClient({ buyerKeyManager, customFetch });
    const lock = await client.reserveInventoryLock("SKU-POW-001", 1);
    assert.equal(callCount, 2);
    assert.equal(lock.lockToken, "lock_pow_solved_777");
    assert.equal(lock.fencingToken, 101);
  });

  it("should verify shipping SLA via endpoint", async () => {
    const mockSla = createMockSlaResponse();
    const customFetch: typeof fetch = async (input) => {
      assert.ok(input.toString().includes("pincode=560001"));
      return new Response(JSON.stringify(mockSla), { status: 200, headers: { "Content-Type": "application/json" } });
    };

    const client = new RazorAgentClient({ buyerKeyManager, customFetch });
    const sla = await client.verifyShippingSla("560001", 500);
    assert.equal(sla.pincode, "560001");
    assert.equal(sla.shippingFeePaise, 5000);
    assert.equal(sla.slaHours, 24);
  });

  it("should execute two-phase settlement with valid AP2 mandate chain", async () => {
    const intentMandate = createTestIntentMandate(buyerKeyManager.getAgentDid(), userKeyManager, "upi_circle_001");
    const cartMandate = createTestCartMandate(merchantKeyManager, "SKU-001", 420000, 75600, 495600, "lock_tok_001");
    const executionMandate = createSignedExecutionMandate(
      {
        intentMandate,
        cartMandate,
        settlementAmountPaise: cartMandate.totalPaise,
        upiCircleToken: intentMandate.upiCircleDelegationToken
      },
      buyerKeyManager
    );

    const mockTransfers = [
      { id: "trf_01", account: "acc_merchant", amount: 495550, currency: "INR" },
      { id: "trf_02", account: "acc_protocol", amount: 50, currency: "INR" }
    ];
    const mockResult = createMockSettlementResult("pay_live_001", 495600, 420000, 75600, mockTransfers);

    const customFetch: typeof fetch = async (_input, init) => {
      const payload = JSON.parse(init?.body as string);
      assert.equal(payload.intentMandate.mandateId, intentMandate.mandateId);
      assert.equal(payload.cartMandate.cartId, cartMandate.cartId);
      return new Response(JSON.stringify(mockResult), { status: 200, headers: { "Content-Type": "application/json" } });
    };

    const client = new RazorAgentClient({ buyerKeyManager, customFetch });
    const result = await client.executeSettlement({
      intentMandate,
      cartMandate,
      executionMandate,
      merchantAccount: "acc_merchant",
      paymentId: "pay_live_001"
    });
    assert.equal(result.status, "captured");
    assert.equal(result.amountPaise, 495600);
  });

  it("should execute autonomous purchase orchestration end-to-end", async () => {
    const intentMandate = createTestIntentMandate(buyerKeyManager.getAgentDid(), userKeyManager, "upi_circle_002");
    const cartMandate = createTestCartMandate(merchantKeyManager, "SKU-002", 100000, 18000, 118000, "lock_tok_002");
    const mockResult = createMockSettlementResult("pay_auto_002", 118000, 100000, 18000);

    const customFetch: typeof fetch = async () =>
      new Response(JSON.stringify(mockResult), { status: 200, headers: { "Content-Type": "application/json" } });

    const client = new RazorAgentClient({ buyerKeyManager, customFetch });
    const result = await client.executeAutonomousPurchase({
      skuId: "SKU-002",
      quantity: 1,
      intentMandate,
      cartMandate,
      merchantAccount: "acc_merchant_auto",
      paymentId: "pay_auto_002"
    });
    assert.equal(result.status, "captured");
    assert.equal(result.paymentId, "pay_auto_002");
  });
});
