import assert from "node:assert/strict";
import test from "node:test";
import type { AddressInfo } from "node:net";
import { createMcpHttpServer } from "../src/http/httpAdapter.js";
import { handleJsonRpcMessage, mcpToolsManifest } from "../src/mcpServerMain.js";
import { handleQuoteRequest } from "../src/http/routeHandlers.js";
import type { JsonRpcRequest } from "../src/types/mcpToolTypes.js";

const testSkuId = "SKU-CHAIR-001";
const testBuyerDid = "did:agent:a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90";
const testPincode = "560034";
const ephemeralPort = 0;

function startTestServer(): Promise<{ baseUrl: string; close: () => Promise<void> }> {
  const server = createMcpHttpServer({
    jsonRpcHandler: (message: unknown) => handleJsonRpcMessage(message as JsonRpcRequest),
    toolsManifest: mcpToolsManifest
  });
  return new Promise((resolve) => {
    server.listen(ephemeralPort, "127.0.0.1", () => {
      const { port } = server.address() as AddressInfo;
      resolve({
        baseUrl: `http://127.0.0.1:${port}`,
        close: () => new Promise((done) => server.close(() => done()))
      });
    });
  });
}

test("health route reports both transports", async () => {
  const { baseUrl, close } = await startTestServer();
  try {
    const response = await fetch(`${baseUrl}/health`);
    assert.equal(response.status, 200);
    const body = await response.json() as { status: string; transports: string[] };
    assert.equal(body.status, "ok");
    assert.deepEqual(body.transports, ["stdio", "http"]);
  } finally {
    await close();
  }
});

test("quote route answers the buyer SDK's camelCase wire shape", async () => {
  const { baseUrl, close } = await startTestServer();
  try {
    const query = new URLSearchParams({
      skuId: testSkuId,
      quantity: "10",
      buyerAgentDid: testBuyerDid,
      deliveryPincode: testPincode
    });
    const response = await fetch(`${baseUrl}/api/v1/quote?${query.toString()}`);
    assert.equal(response.status, 200);
    const quote = await response.json() as Record<string, unknown>;

    // Field names the SDK's `SkuQuote` interface requires -- a snake_case leak breaks the SDK.
    for (const field of ["skuId", "finalUnitPricePaise", "quoteHash", "taxBreakdown", "quantity", "taxableSubtotalPaise"]) {
      assert.ok(field in quote, `quote response missing '${field}'`);
    }
    assert.equal(quote.skuId, testSkuId);
    assert.equal(quote.quantity, 10);
    const tax = quote.taxBreakdown as Record<string, unknown>;
    assert.ok("totalTaxPaise" in tax, "taxBreakdown must be camelCase");
    assert.equal(quote.taxableSubtotalPaise, (quote.finalUnitPricePaise as number) * 10);
  } finally {
    await close();
  }
});

test("lock route reserves stock and returns a signed camelCase token", async () => {
  const { baseUrl, close } = await startTestServer();
  try {
    const quoteQuery = new URLSearchParams({
      skuId: testSkuId, quantity: "2", buyerAgentDid: testBuyerDid, deliveryPincode: testPincode
    });
    const quote = await (await fetch(`${baseUrl}/api/v1/quote?${quoteQuery}`)).json() as { quoteHash: string };

    const response = await fetch(`${baseUrl}/api/v1/lock`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        skuId: testSkuId, quantity: 2, buyerAgentDid: testBuyerDid,
        lockTtlSeconds: 60, quoteHash: quote.quoteHash
      })
    });
    assert.equal(response.status, 200);
    const lock = await response.json() as Record<string, unknown>;
    for (const field of ["lockToken", "fencingToken", "skuId", "quantityLocked", "expiresAtUnixMs", "lockSignature"]) {
      assert.ok(field in lock, `lock response missing '${field}'`);
    }
    assert.equal(lock.quantityLocked, 2);
  } finally {
    await close();
  }
});

test("sla route fills in the merchant origin the SDK does not send", async () => {
  const { baseUrl, close } = await startTestServer();
  try {
    const response = await fetch(`${baseUrl}/api/v1/sla?pincode=${testPincode}&weightGrams=750`);
    assert.equal(response.status, 200);
    const sla = await response.json() as Record<string, unknown>;
    for (const field of ["pincode", "zone", "slaHours", "shippingFeePaise", "weightGrams"]) {
      assert.ok(field in sla, `sla response missing '${field}'`);
    }
    assert.equal(sla.pincode, testPincode);
    assert.equal(sla.weightGrams, 750);
  } finally {
    await close();
  }
});

test("unknown sku maps to 404 rather than a generic 500", async () => {
  const { baseUrl, close } = await startTestServer();
  try {
    const query = new URLSearchParams({
      skuId: "SKU-DOES-NOT-EXIST", quantity: "1",
      buyerAgentDid: testBuyerDid, deliveryPincode: testPincode
    });
    const response = await fetch(`${baseUrl}/api/v1/quote?${query}`);
    assert.equal(response.status, 404);
  } finally {
    await close();
  }
});

test("schema violations map to 422 with issue detail", async () => {
  const { baseUrl, close } = await startTestServer();
  try {
    const query = new URLSearchParams({
      skuId: testSkuId, quantity: "1", buyerAgentDid: "not-a-did", deliveryPincode: testPincode
    });
    const response = await fetch(`${baseUrl}/api/v1/quote?${query}`);
    assert.equal(response.status, 422);
    const body = await response.json() as { error: string; issues?: unknown[] };
    assert.equal(body.error, "ValidationError");
    assert.ok(Array.isArray(body.issues) && body.issues.length > 0);
  } finally {
    await close();
  }
});

test("rpc route reaches the same tool dispatch as stdio", async () => {
  const { baseUrl, close } = await startTestServer();
  try {
    const response = await fetch(`${baseUrl}/rpc`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "tools/list" })
    });
    assert.equal(response.status, 200);
    const body = await response.json() as { result?: { tools?: unknown[] } };
    assert.ok(Array.isArray(body.result?.tools));
  } finally {
    await close();
  }
});

test("CORS preflight is answered so browser-side SDK calls work", async () => {
  const { baseUrl, close } = await startTestServer();
  try {
    const response = await fetch(`${baseUrl}/api/v1/quote`, { method: "OPTIONS" });
    assert.equal(response.status, 204);
    assert.equal(response.headers.get("access-control-allow-origin"), "*");
  } finally {
    await close();
  }
});

test("unknown route is 404 and wrong method on a known route is 405", async () => {
  const { baseUrl, close } = await startTestServer();
  try {
    assert.equal((await fetch(`${baseUrl}/nope`)).status, 404);
    assert.equal((await fetch(`${baseUrl}/api/v1/quote`, { method: "POST", body: "{}" })).status, 405);
  } finally {
    await close();
  }
});

test("quote request names the missing parameter when deliveryPincode is omitted", () => {
    // The buyer SDK types deliveryPincode as optional (QuoteOptions), but the quote tool needs
    // it to choose between a CGST+SGST and an IGST split. Forwarding the absent value as null
    // used to produce "expected string, received null", which named a wire field the SDK caller
    // never wrote. The error must point at the parameter that is actually missing.
    const query = new URLSearchParams({
      skuId: "SKU-CHAIR-001",
      quantity: "1",
      buyerAgentDid: "did:agent:testbuyer"
    });

    assert.throws(
      () => handleQuoteRequest(query),
      (error: unknown) => {
        const issues = (error as { issues?: ReadonlyArray<{ message: string; received?: string; path: ReadonlyArray<string> }> }).issues;
        assert.ok(issues, "Expected a ZodError carrying issues");
        const pincodeIssue = issues.find((issue) => issue.path.includes("delivery_pincode"));
        assert.ok(pincodeIssue, "No issue reported for delivery_pincode");
        // "Required" rather than "Expected string, received null": the caller omitted the
        // parameter, so the error should say it is missing, not that it had the wrong type.
        assert.equal(pincodeIssue.message, "Required");
        assert.notEqual(pincodeIssue.received, "null");
        return true;
      }
  );
});

test("quote request prices a quote when deliveryPincode is supplied", () => {
    const query = new URLSearchParams({
      skuId: "SKU-CHAIR-001",
      quantity: "1",
      buyerAgentDid: "did:agent:testbuyer",
      deliveryPincode: "560034"
    });

  const quote = handleQuoteRequest(query);
  assert.equal(quote.skuId, "SKU-CHAIR-001");
});
