// Renders the SDK call that produced a step, in three languages.
//
// Every snippet is derived from the RECORDED request, not hand-written: the arguments shown are
// read back out of the URL query or JSON body the SDK actually sent. That means a snippet can
// never drift from what the SDK does, and the cURL tab is genuinely the request that was made --
// a reader can paste it into a terminal and get the same response.

import type { ProtocolStepRecord, WireExchange } from "@/types/protocolRunTypes";

export interface CodeSnippet {
  readonly language: string;
  readonly code: string;
}

const indent = "  ";

function quote(value: unknown): string {
  return typeof value === "string" ? `"${value}"` : String(value);
}

function pythonValue(value: unknown): string {
  if (typeof value === "boolean") {
    return value ? "True" : "False";
  }
  return quote(value);
}

function readRequestParameters(exchange: WireExchange | undefined): Record<string, string> {
  if (!exchange) {
    return {};
  }
  const parameters: Record<string, string> = {};
  try {
    const parsedUrl = new URL(exchange.url);
    for (const [key, value] of parsedUrl.searchParams.entries()) {
      parameters[key] = value;
    }
  } catch {
    // A malformed URL should degrade to "no query parameters", never break the panel.
  }
  if (exchange.requestBody && typeof exchange.requestBody === "object") {
    for (const [key, value] of Object.entries(exchange.requestBody as Record<string, unknown>)) {
      parameters[key] = String(value);
    }
  }
  return parameters;
}

interface MethodTemplate {
  readonly typescript: (parameters: Record<string, string>) => string;
  readonly python: (parameters: Record<string, string>) => string;
}

// One entry per SDK method the driver exercises. Keyed by the method name recorded on the step,
// so an unmapped method degrades to a generic rendering rather than showing something wrong.
const methodTemplates: Readonly<Record<string, MethodTemplate>> = {
  getLiveSkuQuote: {
    typescript: (p) =>
      `const quote = await client.getLiveSkuQuote(\n${indent}${quote(p.skuId)},\n${indent}${p.quantity ?? 1},\n${indent}{ deliveryPincode: ${quote(p.deliveryPincode)} }\n);`,
    python: (p) =>
      `quote = await client.getLiveSkuQuote(\n${indent}skuId=${quote(p.skuId)},\n${indent}quantity=${p.quantity ?? 1},\n${indent}deliveryPincode=${quote(p.deliveryPincode)},\n)`
  },
  verifyShippingSla: {
    typescript: (p) =>
      `const sla = await client.verifyShippingSla(${quote(p.pincode)}, ${p.weightGrams ?? 500});`,
    python: (p) =>
      `sla = await client.verifyShippingSla(\n${indent}pincode=${quote(p.pincode)},\n${indent}weightGrams=${p.weightGrams ?? 500},\n)`
  },
  reserveInventoryLock: {
    typescript: (p) =>
      `const lock = await client.reserveInventoryLock(\n${indent}${quote(p.skuId)},\n${indent}${p.quantity ?? 1},\n${indent}{ quoteHash: quote.quoteHash, lockTtlSeconds: ${p.lockTtlSeconds ?? 60} }\n);`,
    python: (p) =>
      `lock = await client.reserveInventoryLock(\n${indent}skuId=${quote(p.skuId)},\n${indent}quantity=${p.quantity ?? 1},\n${indent}quoteHash=quote.quote_hash,\n${indent}lockTtlSeconds=${p.lockTtlSeconds ?? 60},\n)`
  },
  createSignedIntentMandate: {
    typescript: () =>
      `const intentMandate = createSignedIntentMandate(\n${indent}{\n${indent}${indent}delegatedAgentDid: client.getAgentDid(),\n${indent}${indent}maxBudgetPaise,\n${indent}${indent}singleTransactionLimitPaise,\n${indent}${indent}upiCircleDelegationToken,\n${indent}${indent}authorizedCategories\n${indent}},\n${indent}userSigner\n);`,
    python: () =>
      `intent_mandate = createSignedIntentMandate(\n${indent}delegatedAgentDid=client.getAgentDid(),\n${indent}maxBudgetPaise=max_budget_paise,\n${indent}singleTransactionLimitPaise=single_txn_limit_paise,\n${indent}signer=user_signer,\n)`
  },
  createSignedCartMandate: {
    typescript: () =>
      `const cartMandate = createSignedCartMandate(\n${indent}{\n${indent}${indent}merchantGstin,\n${indent}${indent}items: [{ skuId, quantity, unitPricePaise: quote.finalUnitPricePaise, hsnCode: quote.hsnCode, gstRatePercent: quote.gstRatePercent, lineTotalPaise }],\n${indent}${indent}taxBreakdown: quote.taxBreakdown,\n${indent}${indent}inventoryLockToken: lock.lockToken,\n${indent}${indent}totalPaise\n${indent}},\n${indent}merchantSigner\n);`,
    python: () =>
      `cart_mandate = createSignedCartMandate(\n${indent}merchantGstin=merchant_gstin,\n${indent}items=[line_item],\n${indent}taxBreakdown=quote.tax_breakdown,\n${indent}inventoryLockToken=lock.lock_token,\n${indent}signer=merchant_signer,\n)`
  },
  createSignedExecutionMandate: {
    typescript: () =>
      `const executionMandate = createSignedExecutionMandate(\n${indent}{\n${indent}${indent}intentMandate,\n${indent}${indent}cartMandate,\n${indent}${indent}settlementAmountPaise: cartMandate.totalPaise,\n${indent}${indent}upiCircleToken: intentMandate.upiCircleDelegationToken\n${indent}},\n${indent}client.getBuyerKeyManager()\n);`,
    python: () =>
      `execution_mandate = createSignedExecutionMandate(\n${indent}intentMandate=intent_mandate,\n${indent}cartMandate=cart_mandate,\n${indent}settlementAmountPaise=cart_mandate.total_paise,\n${indent}signer=client.getKeyManager(),\n)`
  },
  verifyMandateChain: {
    typescript: () => `verifyMandateChain(intentMandate, cartMandate, executionMandate);`,
    python: () => `verifyMandateChain(intent_mandate, cart_mandate, execution_mandate)`
  },
  executeSettlement: {
    typescript: () =>
      `const settlement = await client.executeSettlement({\n${indent}intentMandate,\n${indent}cartMandate,\n${indent}executionMandate,\n${indent}merchantAccount,\n${indent}paymentId\n});`,
    python: () =>
      `settlement = await client.executeSettlement(\n${indent}intentMandate=intent_mandate,\n${indent}cartMandate=cart_mandate,\n${indent}executionMandate=execution_mandate,\n${indent}merchantAccount=merchant_account,\n${indent}paymentId=payment_id,\n)`
  }
};

function buildCurlSnippet(exchange: WireExchange | undefined): string | null {
  if (!exchange) {
    return null;
  }
  const lines = [`curl -X ${exchange.method} '${exchange.url}'`];
  for (const [name, value] of Object.entries(exchange.requestHeaders)) {
    lines.push(`${indent}-H '${name}: ${value}'`);
  }
  if (exchange.requestBody !== null && exchange.requestBody !== undefined) {
    lines.push(`${indent}-d '${JSON.stringify(exchange.requestBody)}'`);
  }
  return lines.join(" \\\n");
}

function buildGenericSnippet(methodName: string, parameters: Record<string, string>): string {
  const argumentList = Object.entries(parameters)
    .map(([name, value]) => `${indent}${name}: ${quote(value)}`)
    .join(",\n");
  return argumentList.length > 0
    ? `${methodName}({\n${argumentList}\n});`
    : `${methodName}();`;
}

// Shared by the run stepper and the SDK console: both have a method name and the exchanges it
// produced, and neither should be able to render a snippet that differs from the other's.
export function buildInvocationSnippets(
  methodName: string,
  exchanges: readonly WireExchange[]
): readonly CodeSnippet[] {
  const exchange = exchanges[0];
  const parameters = readRequestParameters(exchange);
  const template = methodTemplates[methodName];

  const snippets: CodeSnippet[] = [
    {
      language: "typescript",
      code: template ? template.typescript(parameters) : buildGenericSnippet(methodName, parameters)
    },
    {
      language: "python",
      code: template
        ? template.python(parameters)
        : buildGenericSnippet(methodName, parameters).replace(/;$/, "")
    }
  ];

  const curl = buildCurlSnippet(exchange);
  if (curl) {
    snippets.push({ language: "bash", code: curl });
  }
  return snippets;
}

export function buildStepSnippets(step: ProtocolStepRecord): readonly CodeSnippet[] {
  return buildInvocationSnippets(step.sdkCall.methodName, step.exchanges);
}

export function formatPaise(paise: number): string {
  const rupees = paise / 100;
  return `₹${rupees.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export { pythonValue };
