// Maps a tool name to the implementation that runs it.
//
// Kept apart from mcpServerMain so that adding a tool touches only this file and the manifest,
// and so the entry point stays about transports and JSON-RPC framing rather than growing one
// more branch per capability.
//
// Dispatch, telemetry and error handling deliberately live in mcpServerMain.dispatchToolCall:
// every transport routes through that one function, so instrumentation cannot drift between
// stdio, /rpc and the Streamable HTTP transport.

import {
  toolCreateCartMandate,
  toolEstablishAgentDelegation,
  toolExecuteSettlement,
  toolGetLiveSkuQuote,
  toolReserveInventoryLock,
  toolBrowseCatalog,
  toolNegotiatePrice,
  toolSearchCatalog,
  toolSignExecutionMandate,
  toolVerifyShippingSla
} from "../constants/protocolConstants.js";
import { executeSkuQuote } from "./skuQuoter.js";
import { reserveInventoryLock } from "./inventoryLocker.js";
import { verifyShippingSla } from "./slaVerifier.js";
import { searchCatalog } from "./catalogSearcher.js";
import { browseCatalog } from "./catalogBrowser.js";
import { negotiatePrice } from "./priceNegotiator.js";
import { establishAgentDelegation } from "./delegationEstablisher.js";
import { createCartMandateForDelegation } from "./cartMandateCreator.js";
import { signExecutionMandateForDelegation } from "./executionMandateSigner.js";
import { executeSettlementForDelegation } from "./settlementExecutor.js";
import { defaultCatalogStore } from "../catalog/catalogStore.js";

/**
 * Runs one tool by name. Throws for an unrecognized name; callers that speak JSON-RPC turn
 * that into -32601 rather than an internal error, because an unknown tool is a protocol-level
 * "no such method", not a fault inside a tool.
 */
export async function executeTool(toolName: string, toolArguments: unknown): Promise<unknown> {
  if (toolName === toolGetLiveSkuQuote) {
    return executeSkuQuote(toolArguments, defaultCatalogStore);
  }
  if (toolName === toolReserveInventoryLock) {
    return await reserveInventoryLock(toolArguments, { catalogStore: defaultCatalogStore });
  }
  if (toolName === toolVerifyShippingSla) {
    return verifyShippingSla(toolArguments);
  }
  if (toolName === toolSearchCatalog) {
    return await searchCatalog(toolArguments);
  }
  if (toolName === toolBrowseCatalog) {
    return browseCatalog(toolArguments, defaultCatalogStore);
  }
  if (toolName === toolNegotiatePrice) {
    return await negotiatePrice(toolArguments, defaultCatalogStore);
  }
  if (toolName === toolEstablishAgentDelegation) {
    return await establishAgentDelegation(toolArguments);
  }
  if (toolName === toolCreateCartMandate) {
    return await createCartMandateForDelegation(toolArguments);
  }
  if (toolName === toolSignExecutionMandate) {
    return await signExecutionMandateForDelegation(toolArguments);
  }
  if (toolName === toolExecuteSettlement) {
    return await executeSettlementForDelegation(toolArguments);
  }
  throw new Error(`Tool ${toolName} not recognized`);
}
