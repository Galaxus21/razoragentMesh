import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  handleJsonRpcMessage,
  mcpToolsManifest
} from "../src/mcpServerMain.js";
import {
  toolCreateCartMandate,
  toolEstablishAgentDelegation,
  toolExecuteSettlement,
  toolGetLiveSkuQuote,
  toolReserveInventoryLock,
  toolSearchCatalog,
  toolSignExecutionMandate,
  toolVerifyShippingSla
} from "../src/constants/protocolConstants.js";

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

  it("lists establish_agent_delegation first, because that is what mints the buyer DID", async () => {
    const response = await handleJsonRpcMessage({
      jsonrpc: "2.0",
      id: 21,
      method: "tools/list"
    });

    // Agents read tools/list top to bottom and take it as the call order. Every clean buyer in
    // the dress rehearsal quoted first and had to back up, because in mesh_demo_custodial there
    // is no buyer_agent_id to quote with until this tool has run.
    const result = response.result as { tools: Array<{ name: string }> };
    assert.equal(result.tools[0].name, toolEstablishAgentDelegation);
  });

  it("should advertise every tool an external agent needs, pairing first", async () => {
    const response = await handleJsonRpcMessage({
      jsonrpc: "2.0",
      id: 2,
      method: "tools/list"
    });

    const result = response.result as { tools: Array<{ name: string }> };
    assert.equal(result.tools.length, 8);
    const names = result.tools.map((t) => t.name);
    // search_catalog is the entry point: without it an agent can only quote SKU ids someone
    // already handed it, so a tools/list that omits it leaves the mesh undiscoverable.
    assert.ok(names.includes(toolSearchCatalog));
    assert.ok(names.includes(toolGetLiveSkuQuote));
    assert.ok(names.includes(toolReserveInventoryLock));
    assert.ok(names.includes(toolVerifyShippingSla));
    // The purchase half. Quoting and locking only let an agent price a cart; without these
    // four an external agent still cannot buy, which is the claim the mesh exists to make.
    assert.ok(names.includes(toolEstablishAgentDelegation));
    assert.ok(names.includes(toolCreateCartMandate));
    assert.ok(names.includes(toolSignExecutionMandate));
    assert.ok(names.includes(toolExecuteSettlement));
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
