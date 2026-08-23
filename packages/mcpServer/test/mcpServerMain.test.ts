import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  handleJsonRpcMessage,
  mcpToolsManifest
} from "../src/mcpServerMain.js";
import {
  toolGetLiveSkuQuote,
  toolReserveInventoryLock,
  toolVerifyShippingSla
} from "../src/mcpConstants.js";

describe("McpServerMain JSON-RPC Dispatcher", () => {
  it("should respond to initialize method with server info and tools capability", async () => {
    const response = await handleJsonRpcMessage({
      jsonrpc: "2.0",
      id: 1,
      method: "initialize",
      params: {}
    });

    assert.equal(response.jsonrpc, "2.0");
    assert.equal(response.id, 1);
    const result = response.result as { serverInfo: { name: string; version: string } };
    assert.equal(result.serverInfo.name, "razoragent-mesh-mcp");
  });

  it("should return tools list with all 3 tools defined", async () => {
    const response = await handleJsonRpcMessage({
      jsonrpc: "2.0",
      id: 2,
      method: "tools/list"
    });

    const result = response.result as { tools: Array<{ name: string }> };
    assert.equal(result.tools.length, 3);
    const names = result.tools.map((t) => t.name);
    assert.ok(names.includes(toolGetLiveSkuQuote));
    assert.ok(names.includes(toolReserveInventoryLock));
    assert.ok(names.includes(toolVerifyShippingSla));
  });

  it("should execute tools/call for get_live_sku_quote", async () => {
    const response = await handleJsonRpcMessage({
      jsonrpc: "2.0",
      id: 3,
      method: "tools/call",
      params: {
        name: toolGetLiveSkuQuote,
        arguments: {
          sku_id: "SKU-CHAIR-001",
          quantity: 1,
          buyer_agent_id: "did:agent:test-buyer",
          delivery_pincode: "560001"
        }
      }
    });

    assert.equal(response.id, 3);
    assert.ok(!response.error);
    const result = response.result as { content: Array<{ type: string; text: string }> };
    const content = JSON.parse(result.content[0].text);
    assert.equal(content.sku_id, "SKU-CHAIR-001");
    assert.equal(content.base_unit_price_paise, 420000);
  });

  it("should return method not found for unknown method", async () => {
    const response = await handleJsonRpcMessage({
      jsonrpc: "2.0",
      id: 99,
      method: "unknown/method"
    });

    assert.ok(response.error);
    assert.equal(response.error.code, -32601);
  });
});
