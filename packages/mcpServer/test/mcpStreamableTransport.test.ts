// Covers the MCP Streamable HTTP transport -- the path a judge's own agent uses to reach the
// mesh by URL. The session lifecycle is what distinguishes it from the older /rpc passthrough,
// so these tests exercise the lifecycle rather than just asserting a route answers.

import assert from "node:assert/strict";
import test from "node:test";
import type { AddressInfo } from "node:net";
import { createMcpHttpServer } from "../src/http/httpAdapter.js";
import { dispatchToolCall, handleJsonRpcMessage, mcpToolsManifest } from "../src/mcpServerMain.js";
import { countActiveStreamableSessions } from "../src/http/mcpStreamableTransport.js";
import type { JsonRpcRequest } from "../src/types/mcpToolTypes.js";

const testSkuId = "SKU-CHAIR-001";
const testBuyerDid = "did:agent:a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90";
const testPincode = "560034";
const ephemeralPort = 0;
const protocolVersion = "2025-06-18";
const mcpAccept = "application/json, text/event-stream";

function startTestServer(): Promise<{ baseUrl: string; close: () => Promise<void> }> {
  const server = createMcpHttpServer({
    jsonRpcHandler: (message: unknown) => handleJsonRpcMessage(message as JsonRpcRequest),
    toolsManifest: mcpToolsManifest,
    toolDispatcher: dispatchToolCall
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

/**
 * The transport answers as SSE, so a JSON-RPC reply arrives as `event: message` followed by a
 * `data:` line. Reading only the data lines keeps these tests independent of framing details.
 */
function parseSsePayload(rawBody: string): Record<string, unknown> {
  const dataLine = rawBody
    .split("\n")
    .map((line) => line.trim())
    .find((line) => line.startsWith("data:"));
  assert.ok(dataLine, `no SSE data line in response: ${rawBody.slice(0, 200)}`);
  return JSON.parse(dataLine.slice("data:".length).trim()) as Record<string, unknown>;
}

function postMcp(
  baseUrl: string,
  body: unknown,
  sessionId?: string
): Promise<Response> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: mcpAccept
  };
  if (sessionId) {
    headers["Mcp-Session-Id"] = sessionId;
  }
  return fetch(`${baseUrl}/mcp`, { method: "POST", headers, body: JSON.stringify(body) });
}

function buildInitializeRequest(): Record<string, unknown> {
  return {
    jsonrpc: "2.0",
    id: 1,
    method: "initialize",
    params: {
      protocolVersion,
      capabilities: {},
      clientInfo: { name: "transport-test", version: "1.0.0" }
    }
  };
}

async function openSession(baseUrl: string): Promise<string> {
  const response = await postMcp(baseUrl, buildInitializeRequest());
  assert.equal(response.status, 200);
  const sessionId = response.headers.get("mcp-session-id");
  assert.ok(sessionId, "initialize must issue an Mcp-Session-Id");
  return sessionId;
}

test("initialize opens a session and negotiates the client's protocol version", async () => {
  const { baseUrl, close } = await startTestServer();
  try {
    const response = await postMcp(baseUrl, buildInitializeRequest());
    assert.equal(response.status, 200);
    assert.ok(response.headers.get("mcp-session-id"), "session id must be issued");
    // Browser-based clients cannot read the id unless it is exposed through CORS.
    assert.match(
      response.headers.get("access-control-expose-headers") ?? "",
      /Mcp-Session-Id/i
    );

    const payload = parseSsePayload(await response.text());
    const result = payload.result as Record<string, unknown>;
    assert.equal(result.protocolVersion, protocolVersion);
    assert.deepEqual(result.serverInfo, { name: "razoragent-mesh-mcp", version: "2.0.0" });
  } finally {
    await close();
  }
});

test("a tool call over the session runs the same code as the other transports", async () => {
  const { baseUrl, close } = await startTestServer();
  try {
    const sessionId = await openSession(baseUrl);
    const response = await postMcp(
      baseUrl,
      {
        jsonrpc: "2.0",
        id: 2,
        method: "tools/call",
        params: {
          name: "get_live_sku_quote",
          arguments: {
            sku_id: testSkuId,
            quantity: 2,
            buyer_agent_id: testBuyerDid,
            delivery_pincode: testPincode
          }
        }
      },
      sessionId
    );
    assert.equal(response.status, 200);

    const payload = parseSsePayload(await response.text());
    const result = payload.result as { content: Array<{ text: string }>; isError?: boolean };
    assert.notEqual(result.isError, true, "a valid quote must not be flagged as an error");

    const quote = JSON.parse(result.content[0].text) as Record<string, unknown>;
    assert.equal(quote.sku_id, testSkuId);

    // INV-02: an intra-state quote splits GST into equal halves. Asserted here because this
    // transport must not become a second pricing path -- it shares dispatchToolCall precisely
    // so the money math cannot diverge between how a client happened to connect.
    const tax = quote.tax_breakdown as Record<string, number>;
    assert.equal(tax.cgst_paise, tax.sgst_paise, "CGST and SGST must be equal halves");
    assert.equal(tax.total_tax_paise, tax.cgst_paise + tax.sgst_paise);
  } finally {
    await close();
  }
});

test("a refusing tool reports isError inside the result, not a transport fault", async () => {
  const { baseUrl, close } = await startTestServer();
  try {
    const sessionId = await openSession(baseUrl);
    const response = await postMcp(
      baseUrl,
      {
        jsonrpc: "2.0",
        id: 3,
        method: "tools/call",
        params: {
          name: "get_live_sku_quote",
          arguments: {
            sku_id: "SKU-DOES-NOT-EXIST",
            quantity: 1,
            buyer_agent_id: testBuyerDid,
            delivery_pincode: testPincode
          }
        }
      },
      sessionId
    );

    const payload = parseSsePayload(await response.text());
    assert.ok(!("error" in payload), "a tool refusal must not surface as a JSON-RPC error");
    const result = payload.result as { isError?: boolean; content: Array<{ text: string }> };
    assert.equal(result.isError, true);
    assert.match(result.content[0].text, /not found in catalog/);
  } finally {
    await close();
  }
});

test("an unknown session is rejected rather than silently issued a new one", async () => {
  const { baseUrl, close } = await startTestServer();
  try {
    const response = await postMcp(
      baseUrl,
      { jsonrpc: "2.0", id: 4, method: "tools/list" },
      "00000000-0000-0000-0000-000000000000"
    );
    // Handing back a fresh session would silently discard whatever state the client believed
    // it had, which is harder to diagnose than a refusal.
    assert.equal(response.status, 400);
    const body = await response.json() as { error: string };
    assert.equal(body.error, "InvalidSession");
  } finally {
    await close();
  }
});

test("deleting a session releases it", async () => {
  const { baseUrl, close } = await startTestServer();
  try {
    const before = countActiveStreamableSessions();
    const sessionId = await openSession(baseUrl);
    assert.equal(countActiveStreamableSessions(), before + 1);

    const deletion = await fetch(`${baseUrl}/mcp`, {
      method: "DELETE",
      headers: { "Mcp-Session-Id": sessionId }
    });
    assert.equal(deletion.status, 200);
    assert.equal(
      countActiveStreamableSessions(),
      before,
      "a terminated session must not leak"
    );
  } finally {
    await close();
  }
});

test("a notification on the session is accepted with no body", async () => {
  const { baseUrl, close } = await startTestServer();
  try {
    const sessionId = await openSession(baseUrl);
    const response = await postMcp(
      baseUrl,
      { jsonrpc: "2.0", method: "notifications/initialized" },
      sessionId
    );
    assert.equal(response.status, 202);
    assert.equal((await response.text()).length, 0);
  } finally {
    await close();
  }
});
