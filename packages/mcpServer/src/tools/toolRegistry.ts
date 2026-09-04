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
import { reclaimExpiredDefaultReservations } from "../inventory/redisLockManager.js";

/**
 * Runs one tool by name. Throws for an unrecognized name; callers that speak JSON-RPC turn
 * that into -32601 rather than an internal error, because an unknown tool is a protocol-level
 * "no such method", not a fault inside a tool.
 */
export async function executeTool(
  toolName: string,
  toolArguments: unknown,
  mcpSessionId?: string
): Promise<unknown> {
  if (toolName === toolGetLiveSkuQuote) {
    // Same reclaim the REST adapter runs before it reads stock. Without it the two surfaces
    // answered differently: reserve_inventory_lock sweeps as it acquires, so it would hand out
    // units this quote had just reported as held by a lock that lapsed minutes ago.
    reclaimExpiredDefaultReservations();
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
    // Browsing reads stock twice over: it prints available_stock, and min_stock filters on it.
    // A lapsed reservation left unreclaimed therefore does not merely understate a SKU -- it
    // drops that SKU out of the listing entirely, which is indistinguishable from not selling it.
    reclaimExpiredDefaultReservations();
    return browseCatalog(toolArguments, defaultCatalogStore);
  }
  if (toolName === toolNegotiatePrice) {
    return await negotiatePrice(toolArguments, defaultCatalogStore, undefined, {
      mcpSessionId
    });
  }
  if (toolName === toolEstablishAgentDelegation) {
    // Same session id as the settlement below: it is what makes the buyer's stated budget a
    // ceiling on the session rather than on one delegation the agent can simply replace.
    return await establishAgentDelegation(toolArguments, { mcpSessionId });
  }
  if (toolName === toolCreateCartMandate) {
    return await createCartMandateForDelegation(toolArguments);
  }
  if (toolName === toolSignExecutionMandate) {
    return await signExecutionMandateForDelegation(toolArguments);
  }
  if (toolName === toolExecuteSettlement) {
    // The session id is what lets the duplicate-purchase guard tell "the agent re-paired and
    // bought the same thing again" apart from "a different shopper bought the same thing".
    return await executeSettlementForDelegation(toolArguments, { mcpSessionId });
  }
  throw new Error(`Tool ${toolName} not recognized`);
}
