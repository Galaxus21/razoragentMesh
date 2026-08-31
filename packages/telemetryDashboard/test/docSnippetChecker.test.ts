import { describe, it } from "node:test";
import assert from "node:assert/strict";

import { meshServiceRegistry } from "../src/constants/meshServiceRegistry.js";
import type { CodeFence, SnippetFinding } from "../src/types/docSnippetTypes.js";
import { extractSnippetFacts } from "../src/lib/reference/docSnippetExtractor.js";
import {
  checkFenceAgainstTable,
  collectReceiverTypes,
  type CheckContext,
} from "../src/lib/reference/docSnippetChecks.js";
import {
  checkDocumentedEndpoints,
  checkServiceUrls,
} from "../src/lib/reference/docEndpointChecks.js";
import {
  buildPythonSymbolTable,
  buildTypeScriptSymbolTable,
  loadHttpApiReference,
} from "../src/lib/reference/referenceTables.js";

// The guides used to document buyerAgent.catalog.search(), buyerAgent.cart.create() and a
// four-field constructor the SDK never had. Nothing in the repository could tell, because prose
// is not compiled. These tests are the compiler: they assert the checker fires on each shape of
// that mistake and stays quiet on code it cannot resolve. Whether the guides as published pass
// is asserted separately, in docReference.test.ts.
const typeScript = buildTypeScriptSymbolTable();
const python = buildPythonSymbolTable();
const knownPackageNames = new Set([typeScript.packageName, python.packageName]);
const installerPackageNames = {
  "npm install": typeScript.packageName,
  "pip install": python.packageName,
};

function fenceOf(language: CodeFence["language"], body: string): CodeFence {
  return { slug: "example", sourcePath: "example.mdx", line: 1, language, body };
}

function findingsFor(fence: CodeFence): readonly SnippetFinding[] {
  const table = fence.language === "python" ? python : typeScript;
  const facts = extractSnippetFacts(fence);
  const receiverTypes = new Map<string, string>();
  collectReceiverTypes(facts, table, receiverTypes);
  const context: CheckContext = { table, receiverTypes, knownPackageNames, installerPackageNames };
  return [...checkFenceAgainstTable(fence, facts, context), ...checkServiceUrls(fence, facts)];
}

function messagesFor(fence: CodeFence): string {
  return findingsFor(fence)
    .map((finding) => finding.message)
    .join("\n");
}

describe("The checker catches what the guides actually got wrong", () => {
  it("rejects a method the client does not have", () => {
    const messages = messagesFor(
      fenceOf(
        "typescript",
        "const buyerAgent = new RazorAgentClient({ buyerKeyManager });\n" +
          "await buyerAgent.catalog.search({ query: skuQuery });\n"
      )
    );
    assert.match(messages, /buyerAgent\.catalog/);
    assert.match(messages, /no such member/);
  });

  it("accepts a method the client does have", () => {
    assert.deepEqual(
      findingsFor(
        fenceOf(
          "typescript",
          "const buyerAgent = new RazorAgentClient({ buyerKeyManager });\n" +
            "await buyerAgent.getLiveSkuQuote({ skuId });\n"
        )
      ),
      []
    );
  });

  it("carries the receiver's type across fences, the way a reader reads the page", () => {
    // The construction and the call are in different sections of buyer-sdk.mdx. Scoped to one
    // fence, the checker would have been silent on every call in that guide.
    const receiverTypes = new Map<string, string>();
    const construction = fenceOf("typescript", "const buyerAgent = new RazorAgentClient({});\n");
    collectReceiverTypes(extractSnippetFacts(construction), typeScript, receiverTypes);

    const later = fenceOf("typescript", "await buyerAgent.negotiate({});\n");
    const findings = checkFenceAgainstTable(later, extractSnippetFacts(later), {
      table: typeScript,
      receiverTypes,
      knownPackageNames,
      installerPackageNames,
    });
    assert.equal(findings.length, 1);
    assert.match(findings[0].message, /buyerAgent\.negotiate/);
  });

  it("rejects constructor arguments from a shape the class never had", () => {
    const messages = messagesFor(
      fenceOf(
        "typescript",
        "const buyerAgent = new RazorAgentClient({ agentDid: buyerDid, gatewayUrl: url });\n"
      )
    );
    assert.match(messages, /agentDid, gatewayUrl/);
  });

  it("rejects an import of a name the package does not export", () => {
    const messages = messagesFor(
      fenceOf("typescript", `import { NoSuchThing } from "${typeScript.packageName}";\n`)
    );
    assert.match(messages, /exports no such name/);
  });

  it("rejects an install line naming a package that does not exist", () => {
    const messages = messagesFor(fenceOf("typescript", "npm install @razoragent/buyer-sdk-ts\n"));
    assert.ok(messages.includes(`the package is named ${typeScript.packageName}`), messages);
  });

  it("checks each installer against its own registry", () => {
    // `pip install @razorpay/agent-buyer-sdk` is a real name in the wrong ecosystem.
    const messages = messagesFor(fenceOf("python", `pip install ${typeScript.packageName}\n`));
    assert.ok(messages.includes(python.packageName), messages);
  });

  it("rejects a service URL pointing at another service's port", () => {
    const messages = messagesFor(
      fenceOf(
        "typescript",
        'const buyerAgent = new RazorAgentClient({ x402GatewayUrl: "http://localhost:8000" });\n'
      )
    );
    assert.match(messages, /x402GatewayUrl points at port 8000/);
    assert.match(messages, /8000 is Mandate Engine/);
  });

  it("accepts a service URL on the port the registry records", () => {
    const gateway = meshServiceRegistry.find((service) => service.serviceId === "x402Gateway");
    assert.ok(gateway);
    const url = `http://localhost:${gateway.composePort}`;
    assert.deepEqual(
      findingsFor(
        fenceOf(
          "typescript",
          `const buyerAgent = new RazorAgentClient({ x402GatewayUrl: "${url}" });\n`
        )
      ),
      []
    );
  });
});

describe("The checker stays quiet on code it cannot resolve", () => {
  it("says nothing about a receiver it cannot type", () => {
    // Most fences in the guides construct nothing from the SDK. A checker that guessed here
    // would report every one of them, and would be switched off within a week.
    assert.deepEqual(
      findingsFor(fenceOf("typescript", "const response = await fetch(url);\nresponse.json();\n")),
      []
    );
  });

  it("says nothing about a third-party import", () => {
    assert.deepEqual(findingsFor(fenceOf("python", "from fastapi import FastAPI\n")), []);
  });

  it("ignores a method named only inside a comment", () => {
    assert.deepEqual(
      findingsFor(
        fenceOf(
          "typescript",
          "const buyerAgent = new RazorAgentClient({});\n// buyerAgent.catalog.search() is gone\n"
        )
      ),
      []
    );
  });

  it("treats a DID as one path segment rather than four", () => {
    // /api/v1/merchant/did:razoragent:merchant:9f8e/policy matches {merchantDid}; splitting on
    // the DID's own colons made every merchant route in onboarding.mdx look invented.
    const findings = checkDocumentedEndpoints(
      "example.mdx",
      "curl -X PUT http://localhost:4002/api/v1/merchant/did:razoragent:merchant:9f8e/policy\n",
      loadHttpApiReference()
    );
    assert.deepEqual(findings, []);
  });

  it("reports a route the service genuinely does not serve", () => {
    const findings = checkDocumentedEndpoints(
      "example.mdx",
      "curl http://localhost:4002/api/v1/merchant/invented\n",
      loadHttpApiReference()
    );
    assert.equal(findings.length, 1);
    assert.match(findings[0].message, /is not a route/);
  });

  it("attributes a nested call's keywords to the nested class, not the outer one", () => {
    // RazorAgentClient(config=MeshSlaConfig(mcpBaseUrl=...)) passes one argument, named config.
    // Reading mcpBaseUrl as the client's own argument reported the shape the Python guide
    // recommends as an error against the guide itself.
    assert.deepEqual(
      findingsFor(
        fenceOf(
          "python",
          "buyerAgent = RazorAgentClient(\n" +
            '    config=MeshSlaConfig(mcpBaseUrl="http://localhost:4001"),\n' +
            "    keyManager=keyManager,\n" +
            ")\n"
        )
      ),
      []
    );
  });

  it("still reports an unknown key on the nested class itself", () => {
    // The point of the previous test is precision, not silence: the inner call is still checked,
    // against its own class.
    const messages = messagesFor(
      fenceOf(
        "python",
        "buyerAgent = RazorAgentClient(\n" +
          '    config=MeshSlaConfig(gatewayUrl="http://localhost:8000"),\n' +
          ")\n"
      )
    );
    assert.match(messages, /MeshSlaConfig is constructed with gatewayUrl/);
  });

  it("has no opinion about a port the registry does not know", () => {
    assert.deepEqual(
      checkDocumentedEndpoints(
        "example.mdx",
        "redis://localhost:6379/0 and http://localhost:3000/dashboard\n",
        loadHttpApiReference()
      ),
      []
    );
  });
});
