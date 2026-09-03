// GENERATED FILE -- DO NOT EDIT BY HAND.
//
// Produced by scripts/generateDocsSearchIndex.ts from the sections of docs/**/*.mdx.
// Regenerate with: npm run docs:generate
// A test (test/docsSearch.test.ts) fails if this file no longer matches the docs directory,
// so a stale index cannot ship silently.

import type { DocSearchEntry } from "@/types/docsTypes";

export const docsSearchIndex: readonly DocSearchEntry[] = [
  {
    "route": "/docs/setup",
    "docTitle": "System Setup & Environment Architecture Guide",
    "headingText": "",
    "snippet": "A step-by-step technical guide for Platform Ops and software engineers configuring, booting, and verifying the 7-layer RazorAgent Mesh v2.0 local development...",
    "searchText": " system setup & environment architecture guide a step-by-step technical guide for platform ops and software engineers configuring, booting, and verifying the 7-layer razoragent mesh v2.0 local development and production enclave. ---"
  },
  {
    "route": "/docs/setup#1-system-prerequisites--runtimes",
    "docTitle": "System Setup & Environment Architecture Guide",
    "headingText": "1. System Prerequisites & Runtimes",
    "snippet": "Before launching RazorAgent Mesh, verify your local system meets the following version requirements: - Node.js : v20.10.0+ (LTS) or v22.0.0+ with npm - Python...",
    "searchText": "1. system prerequisites & runtimes system setup & environment architecture guide before launching razoragent mesh, verify your local system meets the following version requirements: - node.js : v20.10.0+ (lts) or v22.0.0+ with npm - python : v3.11.0+ (compatible with 3.12 and 3.13 ) with pip - docker & docker compose : docker v24+ (compose v2.20+ ) - redis : v7.0+ (in-memory state, pub/sub, and distributed locks) - qdrant : v1.7.0+ (vector search engine on port 6333) ---"
  },
  {
    "route": "/docs/setup#2-monorepo-package-topology--localhost-ports",
    "docTitle": "System Setup & Environment Architecture Guide",
    "headingText": "2. Monorepo Package Topology & Localhost Ports",
    "snippet": "When running the mesh locally (via Docker Compose or native processes), each microservice listens on a dedicated localhost port: Localhost Port Microservice...",
    "searchText": "2. monorepo package topology & localhost ports system setup & environment architecture guide when running the mesh locally (via docker compose or native processes), each microservice listens on a dedicated localhost port: localhost port microservice protocol / layer responsibility & role key endpoints --- --- --- --- --- localhost:8000 mandate engine rest / sse (layer 4 & 5) ap2 cryptographic mandate verification (ed25519), 2-phase commit (2pc) multi-party settlement sagas, statutory gstr-1 tax invoicing, and live server-sent events (sse) telemetry stream. get /health post /api/v1/settlement/execute get /api/v1/telemetry/stream localhost:4002 merchant api rest (layer 1) merchant did registration, autonomous negotiation policy configuration, multi-channel catalog ingestion (rest, csv, shopify, erp), domain facets, and dynamic mcx bullion pricing. get /health post /api/v1/merchant/register post /api/v1/merchant/{merchantdid}/catalog localhost:4003 x402 gateway rest (layer 0 & 2) dynamic http 402 negotiation gateway, sha-256 proof-of-work (pow) sybil/anti-spam shield, rubinstein-ståhl bilateral bargaining engine, and ast contract compilation. get /api/v1/mesh/health post /api/v1/mesh/negotiate get /api/v1/mesh/challenge localhost:4001 mcp server json-rpc 2.0 (layer 1) model context protocol server exposing eight tools to autonomous ai buyer agents: discovery ( search catalog ), commerce ( get live sku quote , reserve inventory lock , verify shipping sla ) and purchase ( establish agent delegation , create cart mandate , sign execution mandate , execute settlement ). post /mcp (streamable http) post /rpc stdio pipe localhost:3000 telemetry dashboard web / http (layer 5) real-time next.js 15 web inspector, visual audit trail, dynamic markdown documentation viewer, and universal sku studio. get / get /overview get /docs/setup localhost:6333 qdrant vector db rest / grpc (layer 3) high-speed vector search engine providing approximate nearest neighbor (ann) cosine similarity search and sub-300ms out-of-stock vector cart healing. get /healthz post /collections/merchant catalog/points/search localhost:6379 redis state store tcp (layer 0–4) distributed in-memory cache, atomic lua inventory locking with monotonic fencing tokens, pub/sub event bus, and single-use anti-replay nonce ledger. ping (via redis-cli) ---"
  },
  {
    "route": "/docs/setup#3-environment-configuration-env",
    "docTitle": "System Setup & Environment Architecture Guide",
    "headingText": "3. Environment Configuration (.env)",
    "snippet": "Create your .env file in razoragentMesh/ . It is shorter than you might expect: docker-compose.yml sets each service's port and Redis URL directly, so the only...",
    "searchText": "3. environment configuration (.env) system setup & environment architecture guide create your .env file in razoragentmesh/ . it is shorter than you might expect: docker-compose.yml sets each service's port and redis url directly, so the only values it interpolates from .env are the two signing keys and the dashboard's stream url. running a service outside docker means supplying what compose would otherwise set: every variable above is read by code. earlier revisions of this guide also listed telemetry port , merchant api port , gateway port , mcp server port , qdrant collection name , razorpay webhook secret , ed25519 private key and ap2 gate daily limit paise . nothing reads any of them — setting them has no effect, and ed25519 private key in particular looked like the way to supply a signing key while the code was reading merchant private key hex . they have been removed rather than left to mislead. that list previously also named qdrant host , qdrant port , razorpay key id and razorpay key secret . all four are read by code and are documented above instead: the qdrant pair by the merchant api's auto-vectorizer, the razorpay pair by the mandate engine, where they decide whether settlement runs against the mock ledger or the live route api. ---"
  },
  {
    "route": "/docs/setup#4-bootstrapping-with-docker-compose",
    "docTitle": "System Setup & Environment Architecture Guide",
    "headingText": "4. Bootstrapping with Docker Compose",
    "snippet": "Start the full 7-service mesh in the background:",
    "searchText": "4. bootstrapping with docker compose system setup & environment architecture guide start the full 7-service mesh in the background:"
  },
  {
    "route": "/docs/setup#health-probes--endpoint-verification",
    "docTitle": "System Setup & Environment Architecture Guide",
    "headingText": "Health Probes & Endpoint Verification",
    "snippet": "Verify container health across all service ports: 1. Mandate Engine Settlement Probe Tests the AP2 settlement coordinator, mandate verification enclave, and...",
    "searchText": "health probes & endpoint verification system setup & environment architecture guide verify container health across all service ports: 1. mandate engine settlement probe tests the ap2 settlement coordinator, mandate verification enclave, and gstr-1 tax calculator: 2. merchant registration api probe tests the merchant onboarding service, gstin validator, and catalog ingestion pipeline: 3. x402 dynamic negotiation gateway probe tests the http 402 dynamic negotiation gateway and anti-spam pow solver. unlike the other services, this gateway namespaces its probe under /api/v1/mesh/ -- get /health on port 4003 returns 404: 4. qdrant vector search engine probe ( localhost:6333 ) tests the qdrant ann vector embedding search engine for sub-300ms cart healing: 5. real-time telemetry sse stream ( localhost:8000 ) connects an event listener to the live telemetry event streaming bus: ---"
  },
  {
    "route": "/docs/setup#5-local-development-mode",
    "docTitle": "System Setup & Environment Architecture Guide",
    "headingText": "5. Local Development Mode",
    "snippet": "To run individual packages on your host machine without Docker:",
    "searchText": "5. local development mode system setup & environment architecture guide to run individual packages on your host machine without docker:"
  },
  {
    "route": "/docs/agent-quickstart",
    "docTitle": "Connect Your Own Agent — MCP Quickstart",
    "headingText": "",
    "snippet": "Run the mesh, point your own AI agent at it, and watch a cryptographically signed purchase complete while the dashboard renders each step live. The intended...",
    "searchText": " connect your own agent — mcp quickstart run the mesh, point your own ai agent at it, and watch a cryptographically signed purchase complete while the dashboard renders each step live. the intended setup is two windows side by side: the dashboard on one , your agent on the other . you publish a product in the dashboard, ask your agent to buy it in plain language, and watch the protocol execute in real time. ---"
  },
  {
    "route": "/docs/agent-quickstart#1-start-the-mesh",
    "docTitle": "Connect Your Own Agent — MCP Quickstart",
    "headingText": "1. Start the mesh",
    "snippet": "Seven services. Wait for all of them to report healthy: razoragent catalog seeder showing Exited (0) is correct — it is a one-shot job that loads the fixture...",
    "searchText": "1. start the mesh connect your own agent — mcp quickstart seven services. wait for all of them to report healthy: razoragent catalog seeder showing exited (0) is correct — it is a one-shot job that loads the fixture catalog and stops. open the dashboard at http://localhost:3000/overview . leave it open; it is one half of the demo. ---"
  },
  {
    "route": "/docs/agent-quickstart#2-connect-your-agent",
    "docTitle": "Connect Your Own Agent — MCP Quickstart",
    "headingText": "2. Connect your agent",
    "snippet": "The MCP server speaks two transports. Use whichever your client supports.",
    "searchText": "2. connect your agent connect your own agent — mcp quickstart the mcp server speaks two transports. use whichever your client supports."
  },
  {
    "route": "/docs/agent-quickstart#streamable-http-recommended",
    "docTitle": "Connect Your Own Agent — MCP Quickstart",
    "headingText": "Streamable HTTP (recommended)",
    "snippet": "The mesh is already serving it. Point your client at: For Claude Code:",
    "searchText": "streamable http (recommended) connect your own agent — mcp quickstart the mesh is already serving it. point your client at: for claude code:"
  },
  {
    "route": "/docs/agent-quickstart#stdio",
    "docTitle": "Connect Your Own Agent — MCP Quickstart",
    "headingText": "stdio",
    "snippet": "For clients that spawn a process instead. Build once: Then register this command: MCP TRANSPORT=stdio is required, not optional. Without it the process also...",
    "searchText": "stdio connect your own agent — mcp quickstart for clients that spawn a process instead. build once: then register this command: mcp transport=stdio is required, not optional. without it the process also tries to bind port 4001, which docker already holds, and the session dies before the first tool call. use absolute paths for cwd if your client does not resolve relative ones."
  },
  {
    "route": "/docs/agent-quickstart#confirm-the-connection",
    "docTitle": "Connect Your Own Agent — MCP Quickstart",
    "headingText": "Confirm the connection",
    "snippet": "Ask your agent to list its tools. You should see eight : Tool What it does --- --- search catalog Natural-language product discovery get live sku quote Live...",
    "searchText": "confirm the connection connect your own agent — mcp quickstart ask your agent to list its tools. you should see eight : tool what it does --- --- search catalog natural-language product discovery get live sku quote live price, tax and discount for a sku reserve inventory lock atomic stock reservation with a fencing token verify shipping sla serviceability and delivery-tier check establish agent delegation pairs your agent, issues a signed intent mandate create cart mandate merchant-signed cart at mesh-derived prices sign execution mandate binds intent and cart into an execution mandate execute settlement runs the 2pc settlement saga ---"
  },
  {
    "route": "/docs/agent-quickstart#3-publish-something-to-buy",
    "docTitle": "Connect Your Own Agent — MCP Quickstart",
    "headingText": "3. Publish something to buy",
    "snippet": "In the dashboard, open Merchant Studio and publish a product — give it a title your agent can find in plain language, like Ergonomic Mesh Office Chair with...",
    "searchText": "3. publish something to buy connect your own agent — mcp quickstart in the dashboard, open merchant studio and publish a product — give it a title your agent can find in plain language, like ergonomic mesh office chair with lumbar support . publishing writes the listing to redis and indexes it in qdrant, so it becomes discoverable to search catalog immediately. the seeded fixtures are industrial parts, so anything you add in a different category is easy to pick out of search results. anything you publish lives in the running containers, not in the fixtures — docker compose down -v removes it. ---"
  },
  {
    "route": "/docs/agent-quickstart#4-ask-your-agent-to-buy-it",
    "docTitle": "Connect Your Own Agent — MCP Quickstart",
    "headingText": "4. Ask your agent to buy it",
    "snippet": "Prompt in plain language. The tool descriptions carry the ordering rules, so a capable agent sequences the calls itself: Find me something comfortable to sit...",
    "searchText": "4. ask your agent to buy it connect your own agent — mcp quickstart prompt in plain language. the tool descriptions carry the ordering rules, so a capable agent sequences the calls itself: find me something comfortable to sit on while working at a desk. establish a delegation with a ₹9,000 budget using mesh demo custodial custody, then buy two of the best match, delivering to pincode 560001, state code 29. the agent will work through: pair → discover → quote → lock → cart → sign → settle. pair first. in custodial mode the mesh mints the buyer did, and every later call must use that did — get live sku quote and reserve inventory lock both take it as buyer agent id . the settlement gate rejects a chain whose execution mandate was signed by a different agent than the intent mandate delegated to. one parameter is easy to miss: reserve inventory lock returns its signature under the key signature , but create cart mandate expects it as lock signature . pass the value through unchanged. a successful settlement returns a capture, the route split, and a statutory gstr-1 invoice: the four transfers sum to the grand total, and the tax is recomputed independently by the settlement enclave rather than trusted from the cart. note that tool inputs are snake case while settlement output is camelcase ; the settlement response is the mandate engine's own schema, passed through unmodified."
  },
  {
    "route": "/docs/agent-quickstart#when-the-mesh-refuses",
    "docTitle": "Connect Your Own Agent — MCP Quickstart",
    "headingText": "When the mesh refuses",
    "snippet": "A refusal — replayed nonce, expired inventory lock, budget exceeded, unauthorized category, bad signature — comes back as a tool result with isError set , not...",
    "searchText": "when the mesh refuses connect your own agent — mcp quickstart a refusal — replayed nonce, expired inventory lock, budget exceeded, unauthorized category, bad signature — comes back as a tool result with iserror set , not as a json-rpc error, carrying a machine-readable reason. that distinction matters: a refusal means the protocol worked. an agent that only inspects the json-rpc error field will read a correct refusal as a success. ---"
  },
  {
    "route": "/docs/agent-quickstart#5-watch-it-live",
    "docTitle": "Connect Your Own Agent — MCP Quickstart",
    "headingText": "5. Watch it live",
    "snippet": "Open Protocol Playground - Live Agent ( /playground/live-agent ) in the dashboard window. It groups incoming telemetry by MCP session, so your agent's run...",
    "searchText": "5. watch it live connect your own agent — mcp quickstart open protocol playground - live agent ( /playground/live-agent ) in the dashboard window. it groups incoming telemetry by mcp session, so your agent's run appears as one pipeline: each stage lands as the call is made, with the package that did the work, the arguments sent and the result returned. two agents connected at once stay in separate sessions. the distinction the page is careful about: a refused stage is the protocol working -- a replayed nonce or an over-budget cart being rejected -- and is rendered in accent, never in error red. failed is reserved for something genuinely breaking, such as a service falling over. every tool call publishes mcp tool call and mcp tool result to the telemetry stream, tagged with the mcp session id, so one agent's run groups into one visible sequence. to watch the raw stream: ---"
  },
  {
    "route": "/docs/agent-quickstart#6-key-custody--read-this-before-believing-the-demo",
    "docTitle": "Connect Your Own Agent — MCP Quickstart",
    "headingText": "6. Key custody — read this before believing the demo",
    "snippet": "Signing the Execution Mandate requires the buyer's private key . Whoever holds that key can spend the buyer's money without the buyer. key custody has no...",
    "searchText": "6. key custody — read this before believing the demo connect your own agent — mcp quickstart signing the execution mandate requires the buyer's private key . whoever holds that key can spend the buyer's money without the buyer. key custody has no default; you must state it."
  },
  {
    "route": "/docs/agent-quickstart#agent_held--non-custodial",
    "docTitle": "Connect Your Own Agent — MCP Quickstart",
    "headingText": "agent_held — non-custodial",
    "snippet": "Your agent generates its own Ed25519 keypair and never gives it to the mesh. It proves possession by signing the budget terms at pairing. sign execution...",
    "searchText": "agent_held — non-custodial connect your own agent — mcp quickstart your agent generates its own ed25519 keypair and never gives it to the mesh. it proves possession by signing the budget terms at pairing. sign execution mandate then returns the exact rfc 8785 canonical json and its sha-256 digest, and no signature — your agent signs those bytes itself and passes 128 lowercase hex to execute settlement . the mesh holds no buyer authority at any point. this is the mode where the mandate chain proves what it appears to prove. settle promptly: the nonce ledger rejects an execution mandate signed outside a 65 second window."
  },
  {
    "route": "/docs/agent-quickstart#mesh_demo_custodial--custodial-demo-only",
    "docTitle": "Connect Your Own Agent — MCP Quickstart",
    "headingText": "mesh_demo_custodial — custodial, demo only",
    "snippet": "The mesh mints and holds the buyer key, and returns the private key to you in the pairing response — a custodial demo that hands you the key cannot be mistaken...",
    "searchText": "mesh_demo_custodial — custodial, demo only connect your own agent — mcp quickstart the mesh mints and holds the buyer key, and returns the private key to you in the pairing response — a custodial demo that hands you the key cannot be mistaken for a security boundary. be precise about the cost. in this mode the mesh can sign execution mandates with no human approval. and because the demo mesh also holds the principal key that signs the intent mandate, it can mint itself a fresh delegation with any budget it likes. every signature still verifies; the budget ceiling constrains your agent, not the mesh. the chain proves internal consistency, not that a human authorized the spend. use it when the driving agent cannot perform detached ed25519 signing. use agent held for any claim about what the protocol guarantees."
  },
  {
    "route": "/docs/agent-quickstart#the-production-path",
    "docTitle": "Connect Your Own Agent — MCP Quickstart",
    "headingText": "The production path",
    "snippet": "Split custody: the human's principal key never enters the mesh, the Intent Mandate is signed out-of-band, and the mesh may then hold only an ephemeral session...",
    "searchText": "the production path connect your own agent — mcp quickstart split custody: the human's principal key never enters the mesh, the intent mandate is signed out-of-band, and the mesh may then hold only an ephemeral session key bounded by a delegation it cannot forge. that is what upi circle actually models. ---"
  },
  {
    "route": "/docs/agent-quickstart#7-what-is-enforced-and-what-is-not",
    "docTitle": "Connect Your Own Agent — MCP Quickstart",
    "headingText": "7. What is enforced, and what is not",
    "snippet": "Enforced at settlement, with ₹0 charged on failure: - Budget caps — max budget and single-transaction limit - Delegated agent binding — the execution mandate's...",
    "searchText": "7. what is enforced, and what is not connect your own agent — mcp quickstart enforced at settlement, with ₹0 charged on failure: - budget caps — max budget and single-transaction limit - delegated agent binding — the execution mandate's signer must be the did the intent delegated to - category authorization — cart lines outside authorized categories abort the settlement - arithmetic enclave — line totals, tax and the settlement amount are recomputed, not trusted - inventory lock expiry — a lapsed reservation refuses to settle - nonce replay and cart replay — single-use, enforced by the ledger - mandate expiry and full ed25519 signature-chain verification known limits, stated plainly: - no money moves. without real razorpay credentials the route client is a mock. the split and the invoice are computed for real; the transfer is simulated. - merchant private key hex falls back to a literal committed in the repo. any deployment that does not set it signs cart mandates with a key anyone can read. docker-compose.yml passes an empty value by default, which takes that fallback. - servertime is a client-controlled clock override on the mandate engine's http surface. these mcp tools deliberately do not expose it, but anything calling the engine directly can. - the cumulative-budget ledger fails open if redis is unavailable, leaving per-transaction checks as the only budget defence. - agent identity is ephemeral. keys are never persisted and do not survive a restart. ---"
  },
  {
    "route": "/docs/agent-quickstart#troubleshooting",
    "docTitle": "Connect Your Own Agent — MCP Quickstart",
    "headingText": "Troubleshooting",
    "snippet": "Symptom-by-symptom fixes — port conflicts, handshake failures, degraded search, dark dashboard panels — are in docs/AGENT SETUP TROUBLESHOOTING.md.",
    "searchText": "troubleshooting connect your own agent — mcp quickstart symptom-by-symptom fixes — port conflicts, handshake failures, degraded search, dark dashboard panels — are in docs/agent setup troubleshooting.md."
  },
  {
    "route": "/docs/onboarding",
    "docTitle": "RazorAgent Mesh v2.0 — Developer Onboarding Guide",
    "headingText": "",
    "snippet": "An end-to-end, production-grade technical manual for software engineers, merchant platform developers, and autonomous agent architects integrating with...",
    "searchText": " razoragent mesh v2.0 — developer onboarding guide an end-to-end, production-grade technical manual for software engineers, merchant platform developers, and autonomous agent architects integrating with razoragent mesh v2.0 . ---"
  },
  {
    "route": "/docs/onboarding#table-of-contents",
    "docTitle": "RazorAgent Mesh v2.0 — Developer Onboarding Guide",
    "headingText": "Table of Contents",
    "snippet": "1. Executive Overview & Protocol Topology 2. System Prerequisites & Environment Setup 3. Cryptographic Key Management & DID Minting 4. Step-by-Step Merchant...",
    "searchText": "table of contents razoragent mesh v2.0 — developer onboarding guide 1. executive overview & protocol topology 2. system prerequisites & environment setup 3. cryptographic key management & did minting 4. step-by-step merchant onboarding - step 1: merchant did & razorpay route registration - step 2: autonomous negotiation policy configuration - step 3: multi-channel catalog ingestion - step 4: universal product protocol & domain facets - step 5: dynamic bullion pricing & mcx spot oracle - step 6: statutory hsn chapter resolution & gst tax rules - step 7: programmatic sku authoring & publishing 5. step-by-step buyer agent onboarding - step 1: buyer sdk installation - step 2: key management & ap2 budget gate limits - step 3: user spending intent mandate ( ) creation - step 4: mcp product discovery & 4-tier discount stacking - step 5: http 402 pow challenge resolution & b2b bargaining - step 6: atomic stock reservation with monotonic fencing - step 7: cart ( ), execution ( ), and amendment ( ) mandates - step 8: two-phase commit (2pc) settlement saga execution 6. complete executable end-to-end implementations - typescript implementation - python implementation 7. error handling, http status codes & troubleshooting ---"
  },
  {
    "route": "/docs/onboarding#1-executive-overview--protocol-topology",
    "docTitle": "RazorAgent Mesh v2.0 — Developer Onboarding Guide",
    "headingText": "1. Executive Overview & Protocol Topology",
    "snippet": "RazorAgent Mesh v2.0 is an open, decentralized agentic commerce protocol designed for autonomous machine-to-machine transactions over Indian sovereign payment...",
    "searchText": "1. executive overview & protocol topology razoragent mesh v2.0 — developer onboarding guide razoragent mesh v2.0 is an open, decentralized agentic commerce protocol designed for autonomous machine-to-machine transactions over indian sovereign payment rails (upi circle, razorpay route) and tax frameworks (gst rule 46 / gstr-1)."
  },
  {
    "route": "/docs/onboarding#protocol-architecture",
    "docTitle": "RazorAgent Mesh v2.0 — Developer Onboarding Guide",
    "headingText": "Protocol Architecture",
    "snippet": "The protocol operates across 5 distinct cryptographic, discovery, negotiation, and settlement layers:",
    "searchText": "protocol architecture razoragent mesh v2.0 — developer onboarding guide the protocol operates across 5 distinct cryptographic, discovery, negotiation, and settlement layers:"
  },
  {
    "route": "/docs/onboarding#core-mathematical--cryptographic-invariants",
    "docTitle": "RazorAgent Mesh v2.0 — Developer Onboarding Guide",
    "headingText": "Core Mathematical & Cryptographic Invariants",
    "snippet": "Invariant Name Formulation / Specification Enforcement Point --- --- --- --- INV-01 Integer Paise Arithmetic All monetary values represented in positive...",
    "searchText": "core mathematical & cryptographic invariants razoragent mesh v2.0 — developer onboarding guide invariant name formulation / specification enforcement point --- --- --- --- inv-01 integer paise arithmetic all monetary values represented in positive integers ( paise, where ₹1.00 = 100 paise). floating-point floats are strictly rejected. arithmeticenclave.py , jcscanonicalizer.ts inv-02 equal-half gst division intra-state: and . inter-state: and . total tax is defined as the sum of the levies. both halves come from the identical expression, so they are equal by construction; deriving one as the remainder of the other would produce an illegal 2%/3% split on odd slabs such as 5%. arithmeticenclave.py , pricingengine.ts inv-03 ed25519 canonical signatures detached 64-byte ed25519 cryptographic signatures generated over rfc 8785 json canonicalization scheme (jcs) byte buffers. agentkeymanager , ed25519verifier inv-04 ap2 budget gate invariant with category whitelisting. budgetgate.py , agentmandatebuilder.ts inv-05 anti-replay monotonic nonces nonces are single-use uuidv4/hex strings recorded via redis atomic setnx with a 120s ttl and a tight clock drift window . nonceledger.py inv-06 negotiation monotonicity buyer bids are strictly non-decreasing ( ); seller asks are strictly non-increasing ( ), bounded by seller margin floor. bidstatemachine.py inv-07 atomic inventory fencing redis lua script executes atomic stock decrement and increments a monotonic fencing token, preventing concurrent double-allocation. inventorylocker.ts , redislockmanager.ts ---"
  },
  {
    "route": "/docs/onboarding#2-system-prerequisites--environment-setup",
    "docTitle": "RazorAgent Mesh v2.0 — Developer Onboarding Guide",
    "headingText": "2. System Prerequisites & Environment Setup",
    "snippet": "",
    "searchText": "2. system prerequisites & environment setup razoragent mesh v2.0 — developer onboarding guide "
  },
  {
    "route": "/docs/onboarding#21-hardware--runtime-requirements",
    "docTitle": "RazorAgent Mesh v2.0 — Developer Onboarding Guide",
    "headingText": "2.1 Hardware & Runtime Requirements",
    "snippet": "- Node.js : v20.10.0+ (LTS) with npm v10+ - Python : v3.11.0+ (compatible with Python 3.12 and 3.13) with pip and virtualenv - Docker & Docker Compose : Docker...",
    "searchText": "2.1 hardware & runtime requirements razoragent mesh v2.0 — developer onboarding guide - node.js : v20.10.0+ (lts) with npm v10+ - python : v3.11.0+ (compatible with python 3.12 and 3.13) with pip and virtualenv - docker & docker compose : docker v24+ (compose v2.20+) - redis : v7.0+ (standalone or clustered with pub/sub support) - qdrant : v1.7.0+ (vector search engine running on port 6333)"
  },
  {
    "route": "/docs/onboarding#22-repository-layout",
    "docTitle": "RazorAgent Mesh v2.0 — Developer Onboarding Guide",
    "headingText": "2.2 Repository Layout",
    "snippet": "",
    "searchText": "2.2 repository layout razoragent mesh v2.0 — developer onboarding guide "
  },
  {
    "route": "/docs/onboarding#23-environment-variable-template-env",
    "docTitle": "RazorAgent Mesh v2.0 — Developer Onboarding Guide",
    "headingText": "2.3 Environment Variable Template (.env)",
    "snippet": "Create a .env file in razoragentMesh/ based on the template below:",
    "searchText": "2.3 environment variable template (.env) razoragent mesh v2.0 — developer onboarding guide create a .env file in razoragentmesh/ based on the template below:"
  },
  {
    "route": "/docs/onboarding#24-launching-local-infrastructure",
    "docTitle": "RazorAgent Mesh v2.0 — Developer Onboarding Guide",
    "headingText": "2.4 Launching Local Infrastructure",
    "snippet": "Start Redis and Qdrant via Docker Compose: Verify service health: ---",
    "searchText": "2.4 launching local infrastructure razoragent mesh v2.0 — developer onboarding guide start redis and qdrant via docker compose: verify service health: ---"
  },
  {
    "route": "/docs/onboarding#3-cryptographic-key-management--did-minting",
    "docTitle": "RazorAgent Mesh v2.0 — Developer Onboarding Guide",
    "headingText": "3. Cryptographic Key Management & DID Minting",
    "snippet": "All actors in the mesh (Merchants, Buyer Agents, CFO/Users) are identified by Decentralized Identifiers (DIDs) rooted in Ed25519 public verification keys.",
    "searchText": "3. cryptographic key management & did minting razoragent mesh v2.0 — developer onboarding guide all actors in the mesh (merchants, buyer agents, cfo/users) are identified by decentralized identifiers (dids) rooted in ed25519 public verification keys."
  },
  {
    "route": "/docs/onboarding#31-did-specifications",
    "docTitle": "RazorAgent Mesh v2.0 — Developer Onboarding Guide",
    "headingText": "3.1 DID Specifications",
    "snippet": "Actor Type DID Format Public Key Component Example --- --- --- --- Merchant did:razoragent:merchant: First 16 hex characters of Ed25519 Verify Key...",
    "searchText": "3.1 did specifications razoragent mesh v2.0 — developer onboarding guide actor type did format public key component example --- --- --- --- merchant did:razoragent:merchant: first 16 hex characters of ed25519 verify key did:razoragent:merchant:9f8e7d6c5b4a3210 buyer agent did:razoragent:buyer: first 16 hex characters of ed25519 verify key did:razoragent:buyer:ad1b82a9cce6d365 user / cfo did:razoragent:user: first 16 hex characters of ed25519 verify key did:razoragent:user:ec89f8790fa0bc33"
  },
  {
    "route": "/docs/onboarding#32-keypair-generation--signing-python--pynacl",
    "docTitle": "RazorAgent Mesh v2.0 — Developer Onboarding Guide",
    "headingText": "3.2 Keypair Generation & Signing (Python / PyNaCl)",
    "snippet": "",
    "searchText": "3.2 keypair generation & signing (python / pynacl) razoragent mesh v2.0 — developer onboarding guide "
  },
  {
    "route": "/docs/onboarding#33-keypair-generation--signing-typescript--tweetnacl",
    "docTitle": "RazorAgent Mesh v2.0 — Developer Onboarding Guide",
    "headingText": "3.3 Keypair Generation & Signing (TypeScript / TweetNaCl)",
    "snippet": "---",
    "searchText": "3.3 keypair generation & signing (typescript / tweetnacl) razoragent mesh v2.0 — developer onboarding guide ---"
  },
  {
    "route": "/docs/onboarding#4-step-by-step-merchant-onboarding",
    "docTitle": "RazorAgent Mesh v2.0 — Developer Onboarding Guide",
    "headingText": "4. Step-by-Step Merchant Onboarding",
    "snippet": "The Merchant Onboarding flow registers regulatory credentials, provisions autonomous negotiation parameters, ingests multi-vertical product catalogs,...",
    "searchText": "4. step-by-step merchant onboarding razoragent mesh v2.0 — developer onboarding guide the merchant onboarding flow registers regulatory credentials, provisions autonomous negotiation parameters, ingests multi-vertical product catalogs, configures dynamic bullion pricing rules, and publishes skus to the mesh."
  },
  {
    "route": "/docs/onboarding#step-1-merchant-did--razorpay-route-registration",
    "docTitle": "RazorAgent Mesh v2.0 — Developer Onboarding Guide",
    "headingText": "Step 1: Merchant DID & Razorpay Route Registration",
    "snippet": "Merchants submit statutory GSTIN details, their registered Razorpay Route linked account ( acc ... ), contact email, and dispatch origin pincode to the...",
    "searchText": "step 1: merchant did & razorpay route registration razoragent mesh v2.0 — developer onboarding guide merchants submit statutory gstin details, their registered razorpay route linked account ( acc ... ), contact email, and dispatch origin pincode to the merchantapi service on port 4002 . validation rules 1. gstin checksum : verified via indian gst luhn mod-36 algorithm ( ^[0-9]{2}[a-z]{5}[0-9]{4}[a-z]{1}[1-9a-z]{1}z[0-9a-z]{1}$ ). 2. razorpay route account : must match prefix acc with minimum length 14. 3. origin pincode : 6 digits starting with 1-9 ( ^[1-9][0-9]{5}$ ). registration request registration response (http 201 created) ---"
  },
  {
    "route": "/docs/onboarding#step-2-autonomous-negotiation-policy-configuration",
    "docTitle": "RazorAgent Mesh v2.0 — Developer Onboarding Guide",
    "headingText": "Step 2: Autonomous Negotiation Policy Configuration",
    "snippet": "Merchants define their automated concession limits for bilateral bargaining with AI buyer agents. The negotiation state machine enforces these boundaries...",
    "searchText": "step 2: autonomous negotiation policy configuration razoragent mesh v2.0 — developer onboarding guide merchants define their automated concession limits for bilateral bargaining with ai buyer agents. the negotiation state machine enforces these boundaries server-side. policy parameters - marginfloorbps : maximum discount floor in basis points (e.g., 800 = 8.00% max discount). - minimumorderquantity : minimum order quantity eligible for dynamic bargaining. - autoacceptspreadpaise : spread in paise below which a counter-offer is automatically accepted. - maxnegotiationturns : maximum allowable rubinstein-ståhl bargaining turns ( , default 5 ). policy request ---"
  },
  {
    "route": "/docs/onboarding#step-3-multi-channel-catalog-ingestion",
    "docTitle": "RazorAgent Mesh v2.0 — Developer Onboarding Guide",
    "headingText": "Step 3: Multi-Channel Catalog Ingestion",
    "snippet": "RazorAgent Mesh provides four distinct programmatic ingestion adapters: A. Direct Single-SKU REST Ingestion Endpoint: POST...",
    "searchText": "step 3: multi-channel catalog ingestion razoragent mesh v2.0 — developer onboarding guide razoragent mesh provides four distinct programmatic ingestion adapters: a. direct single-sku rest ingestion endpoint: post /api/v1/merchant/{merchantdid}/catalog b. bulk csv catalog batch upload (up to 500 rows/batch) endpoint: post /api/v1/merchant/{merchantdid}/bulk-csv create catalog batch.csv : upload csv via curl: c. shopify webhook ingestion endpoint: post /api/v1/merchant/{merchantdid}/shopify-sync receives standard shopify products/create and products/update webhooks. variants are automatically mapped to sku format shopify-{productid}-{variantid} and shopify tags are parsed into domain facets ( promo:... , allergens:... , salt:... , 18k / 22k / 24k ). d. erp delta stock & price sync endpoint: post /api/v1/merchant/{merchantdid}/erp-sync ---"
  },
  {
    "route": "/docs/onboarding#step-4-universal-product-protocol--domain-facets",
    "docTitle": "RazorAgent Mesh v2.0 — Developer Onboarding Guide",
    "headingText": "Step 4: Universal Product Protocol & Domain Facets",
    "snippet": "RazorAgent Mesh supports 4 multi-industry domain facets: ---",
    "searchText": "step 4: universal product protocol & domain facets razoragent mesh v2.0 — developer onboarding guide razoragent mesh supports 4 multi-industry domain facets: ---"
  },
  {
    "route": "/docs/onboarding#step-5-dynamic-bullion-pricing--mcx-spot-oracle",
    "docTitle": "RazorAgent Mesh v2.0 — Developer Onboarding Guide",
    "headingText": "Step 5: Dynamic Bullion Pricing & MCX Spot Oracle",
    "snippet": "For precious metals (Gold 24K, Gold 22K, Silver), merchants can attach a DynamicPricingRule to evaluate real-time quotations linked directly to MCX spot feeds....",
    "searchText": "step 5: dynamic bullion pricing & mcx spot oracle razoragent mesh v2.0 — developer onboarding guide for precious metals (gold 24k, gold 22k, silver), merchants can attach a dynamicpricingrule to evaluate real-time quotations linked directly to mcx spot feeds. mathematical valuation formula bullion sku payload with dynamic pricing attachment ---"
  },
  {
    "route": "/docs/onboarding#step-6-statutory-hsn-chapter-resolution--gst-tax-rules",
    "docTitle": "RazorAgent Mesh v2.0 — Developer Onboarding Guide",
    "headingText": "Step 6: Statutory HSN Chapter Resolution & GST Tax Rules",
    "snippet": "RazorAgent Mesh enforces statutory GST rates based on Indian HSN/SAC classifications: Category HSN Code Statutory GST Rate Tax Split (Intra-State) Tax Split...",
    "searchText": "step 6: statutory hsn chapter resolution & gst tax rules razoragent mesh v2.0 — developer onboarding guide razoragent mesh enforces statutory gst rates based on indian hsn/sac classifications: category hsn code statutory gst rate tax split (intra-state) tax split (inter-state) --- --- --- --- --- precious jewelry 7113 3% 1.5% cgst + 1.5% sgst 3.0% igst apparel (< ₹1,000) 6109 5% 2.5% cgst + 2.5% sgst 5.0% igst apparel ( ₹1,000) 6203 12% 6.0% cgst + 6.0% sgst 12.0% igst pharmaceuticals 3004 5% / 12% 2.5% cgst + 2.5% sgst 5.0% / 12.0% igst packaged foods (fmcg) 2106 12% / 18% 6.0% cgst + 6.0% sgst 12.0% / 18.0% igst electronics & hardware 8471 18% 9.0% cgst + 9.0% sgst 18.0% igst luxury / automobiles 8703 28% 14.0% cgst + 14.0% sgst 28.0% igst ---"
  },
  {
    "route": "/docs/onboarding#step-7-programmatic-sku-authoring--publishing",
    "docTitle": "RazorAgent Mesh v2.0 — Developer Onboarding Guide",
    "headingText": "Step 7: Programmatic SKU Authoring & Publishing",
    "snippet": "Merchants can use a lightweight Python or Node.js publishing script to automate catalog registration and live updates: ---",
    "searchText": "step 7: programmatic sku authoring & publishing razoragent mesh v2.0 — developer onboarding guide merchants can use a lightweight python or node.js publishing script to automate catalog registration and live updates: ---"
  },
  {
    "route": "/docs/onboarding#5-step-by-step-buyer-agent-onboarding",
    "docTitle": "RazorAgent Mesh v2.0 — Developer Onboarding Guide",
    "headingText": "5. Step-by-Step Buyer Agent Onboarding",
    "snippet": "AI Buyer Agents execute automated purchasing workflows within principal-delegated spending constraints.",
    "searchText": "5. step-by-step buyer agent onboarding razoragent mesh v2.0 — developer onboarding guide ai buyer agents execute automated purchasing workflows within principal-delegated spending constraints."
  },
  {
    "route": "/docs/onboarding#step-1-buyer-sdk-installation",
    "docTitle": "RazorAgent Mesh v2.0 — Developer Onboarding Guide",
    "headingText": "Step 1: Buyer SDK Installation",
    "snippet": "TypeScript / Node.js Python ---",
    "searchText": "step 1: buyer sdk installation razoragent mesh v2.0 — developer onboarding guide typescript / node.js python ---"
  },
  {
    "route": "/docs/onboarding#step-2-key-management--ap2-budget-gate-limits",
    "docTitle": "RazorAgent Mesh v2.0 — Developer Onboarding Guide",
    "headingText": "Step 2: Key Management & AP2 Budget Gate Limits",
    "snippet": "Initialize the AgentKeyManager and configure the human principal's spending delegation limits: ---",
    "searchText": "step 2: key management & ap2 budget gate limits razoragent mesh v2.0 — developer onboarding guide initialize the agentkeymanager and configure the human principal's spending delegation limits: ---"
  },
  {
    "route": "/docs/onboarding#step-3-user-spending-intent-mandate-m_i-creation",
    "docTitle": "RazorAgent Mesh v2.0 — Developer Onboarding Guide",
    "headingText": "Step 3: User Spending Intent Mandate ($M_I$) Creation",
    "snippet": "The user signs an immutable Intent Mandate ( ) establishing strict financial and category limits: ---",
    "searchText": "step 3: user spending intent mandate ($m_i$) creation razoragent mesh v2.0 — developer onboarding guide the user signs an immutable intent mandate ( ) establishing strict financial and category limits: ---"
  },
  {
    "route": "/docs/onboarding#step-4-mcp-product-discovery--4-tier-discount-stacking",
    "docTitle": "RazorAgent Mesh v2.0 — Developer Onboarding Guide",
    "headingText": "Step 4: MCP Product Discovery & 4-Tier Discount Stacking",
    "snippet": "The buyer agent queries the Layer 1 MCP tool get live sku quote and receives a dynamic quote with automated discount stacking and tax breakdown. 4-Tier...",
    "searchText": "step 4: mcp product discovery & 4-tier discount stacking razoragent mesh v2.0 — developer onboarding guide the buyer agent queries the layer 1 mcp tool get live sku quote and receives a dynamic quote with automated discount stacking and tax breakdown. 4-tier auto-discount pipeline 1. tier 1: volume discount : basis points based on requested quantity. 2. tier 2: campaign promo : promo codes (e.g. festive10 , 10% off capped at ₹20.00). 3. tier 3: upi rail incentive : flat ₹1.50 (150 paise) incentive on upi circle rail. 4. tier 4: corporate partner promo : additional 5% discount for corporate accounts ( corp 5pct ). ---"
  },
  {
    "route": "/docs/onboarding#step-5-http-402-pow-challenge-resolution--b2b-bargaining",
    "docTitle": "RazorAgent Mesh v2.0 — Developer Onboarding Guide",
    "headingText": "Step 5: HTTP 402 PoW Challenge Resolution & B2B Bargaining",
    "snippet": "If the SKU requires dynamic negotiation, the gateway challenges the buyer with an HTTP 402 Payment Required status containing a cryptographic SHA-256...",
    "searchText": "step 5: http 402 pow challenge resolution & b2b bargaining razoragent mesh v2.0 — developer onboarding guide if the sku requires dynamic negotiation, the gateway challenges the buyer with an http 402 payment required status containing a cryptographic sha-256 proof-of-work puzzle. ---"
  },
  {
    "route": "/docs/onboarding#step-6-atomic-stock-reservation-with-monotonic-fencing",
    "docTitle": "RazorAgent Mesh v2.0 — Developer Onboarding Guide",
    "headingText": "Step 6: Atomic Stock Reservation with Monotonic Fencing",
    "snippet": "The buyer locks stock for 60 seconds via reserve inventory lock . The enclave executes an atomic Redis Lua script, returning a lock token and monotonic fencing...",
    "searchText": "step 6: atomic stock reservation with monotonic fencing razoragent mesh v2.0 — developer onboarding guide the buyer locks stock for 60 seconds via reserve inventory lock . the enclave executes an atomic redis lua script, returning a lock token and monotonic fencing token: ---"
  },
  {
    "route": "/docs/onboarding#step-7-cart-m_c-execution-m_e-and-amendment-m_a-mandates",
    "docTitle": "RazorAgent Mesh v2.0 — Developer Onboarding Guide",
    "headingText": "Step 7: Cart ($M_C$), Execution ($M_E$), and Amendment ($M_A$) Mandates",
    "snippet": "---",
    "searchText": "step 7: cart ($m_c$), execution ($m_e$), and amendment ($m_a$) mandates razoragent mesh v2.0 — developer onboarding guide ---"
  },
  {
    "route": "/docs/onboarding#step-8-two-phase-commit-2pc-settlement-saga-execution",
    "docTitle": "RazorAgent Mesh v2.0 — Developer Onboarding Guide",
    "headingText": "Step 8: Two-Phase Commit (2PC) Settlement Saga Execution",
    "snippet": "The buyer agent submits the mandate chain to POST /api/v1/settlement/execute . ---",
    "searchText": "step 8: two-phase commit (2pc) settlement saga execution razoragent mesh v2.0 — developer onboarding guide the buyer agent submits the mandate chain to post /api/v1/settlement/execute . ---"
  },
  {
    "route": "/docs/onboarding#6-complete-executable-end-to-end-implementations",
    "docTitle": "RazorAgent Mesh v2.0 — Developer Onboarding Guide",
    "headingText": "6. Complete Executable End-to-End Implementations",
    "snippet": "",
    "searchText": "6. complete executable end-to-end implementations razoragent mesh v2.0 — developer onboarding guide "
  },
  {
    "route": "/docs/onboarding#typescript-implementation",
    "docTitle": "RazorAgent Mesh v2.0 — Developer Onboarding Guide",
    "headingText": "TypeScript Implementation",
    "snippet": "---",
    "searchText": "typescript implementation razoragent mesh v2.0 — developer onboarding guide ---"
  },
  {
    "route": "/docs/onboarding#python-implementation",
    "docTitle": "RazorAgent Mesh v2.0 — Developer Onboarding Guide",
    "headingText": "Python Implementation",
    "snippet": "---",
    "searchText": "python implementation razoragent mesh v2.0 — developer onboarding guide ---"
  },
  {
    "route": "/docs/onboarding#7-error-handling-http-status-codes--troubleshooting",
    "docTitle": "RazorAgent Mesh v2.0 — Developer Onboarding Guide",
    "headingText": "7. Error Handling, HTTP Status Codes & Troubleshooting",
    "snippet": "",
    "searchText": "7. error handling, http status codes & troubleshooting razoragent mesh v2.0 — developer onboarding guide "
  },
  {
    "route": "/docs/onboarding#71-common-http-status-codes",
    "docTitle": "RazorAgent Mesh v2.0 — Developer Onboarding Guide",
    "headingText": "7.1 Common HTTP Status Codes",
    "snippet": "HTTP Code Error Condition Root Cause & Resolution --- --- --- 400 Bad Request InvalidGstinException GSTIN fails Indian Luhn Mod-36 checksum. Verify format...",
    "searchText": "7.1 common http status codes razoragent mesh v2.0 — developer onboarding guide http code error condition root cause & resolution --- --- --- 400 bad request invalidgstinexception gstin fails indian luhn mod-36 checksum. verify format 27aaacg0123m1z5 . 400 bad request budgetexceededviolation cart total exceeds . adjust intent budget or request price concession. 400 bad request signatureverificationfailedexception ed25519 signature invalid over rfc 8785 canonical bytes. re-check signing key and payload canonicalizer. 402 payment required http402requirederror ingress pow challenge or micro-escrow debit required. ensure sdk has autosolvepow=true . 404 not found catalognotfoundexception requested skuid does not exist for the specified merchantdid . 409 conflict noncereplayexception the nonce in was previously used or timestamp drifted outside . 409 conflict insufficientstockexception inventory count is below requested quantity. intercept and route to vector healer. 502 bad gateway settlementcompensationtriggeredexception razorpay route split payout failed. automatic lifo rollback was executed and queued to dlq."
  },
  {
    "route": "/docs/onboarding#72-troubleshooting-guide",
    "docTitle": "RazorAgent Mesh v2.0 — Developer Onboarding Guide",
    "headingText": "7.2 Troubleshooting Guide",
    "snippet": "1. \"Nonce replay detected or timestamp drift\" - Cause : Server timestamp and client timestamp differ by more than 5 seconds in the past or 60 seconds in the...",
    "searchText": "7.2 troubleshooting guide razoragent mesh v2.0 — developer onboarding guide 1. \"nonce replay detected or timestamp drift\" - cause : server timestamp and client timestamp differ by more than 5 seconds in the past or 60 seconds in the future. - fix : synchronize client host clocks using ntp ( sudo apt install chrony && chronyd -q ). 2. \"floating point values rejected in jcs canonicalizer\" - cause : monetary inputs contain floats (e.g. 99.50 instead of 9950 ). - fix : adhere strictly to inv-01 : pass all prices, taxes, and discounts in integer paise. 3. \"stalepricequoteexception: price quote is stale\" - cause : dynamic bullion quote exceeded its maxquotettlseconds (default 60s). - fix : refresh quote via get live sku quote immediately prior to issuing and ."
  },
  {
    "route": "/docs/buyer-sdk",
    "docTitle": "AI Buyer Agent SDK & AP2 Protocol Guide",
    "headingText": "",
    "snippet": "A developer guide for integrating autonomous AI buyer agents with Ed25519 mandate signing, live discount stacking, and fenced inventory reservation. Every...",
    "searchText": " ai buyer agent sdk & ap2 protocol guide a developer guide for integrating autonomous ai buyer agents with ed25519 mandate signing, live discount stacking, and fenced inventory reservation. every snippet on this page is checked against the sdk's generated symbol table by npm run docs:verify , run locally -- this repository has no ci by design, so the checks are commands a person runs. a method, constructor argument or service port named here that the sdk does not have fails that command. link targets are checked separately by python scripts/verifydoclinks.py --check , because docs:verify reads snippets and not links. ---"
  },
  {
    "route": "/docs/buyer-sdk#1-sdk-installation",
    "docTitle": "AI Buyer Agent SDK & AP2 Protocol Guide",
    "headingText": "1. SDK Installation",
    "snippet": "Install the standalone buyer agent SDK for your target runtime: ---",
    "searchText": "1. sdk installation ai buyer agent sdk & ap2 protocol guide install the standalone buyer agent sdk for your target runtime: ---"
  },
  {
    "route": "/docs/buyer-sdk#2-client-initialization--key-management",
    "docTitle": "AI Buyer Agent SDK & AP2 Protocol Guide",
    "headingText": "2. Client Initialization & Key Management",
    "snippet": "The client takes a key manager and the addresses of the mesh services it talks to. There is no single base URL: quotes and locks come from the MCP Server,...",
    "searchText": "2. client initialization & key management ai buyer agent sdk & ap2 protocol guide the client takes a key manager and the addresses of the mesh services it talks to. there is no single base url: quotes and locks come from the mcp server, settlement from the mandate engine, and http 402 micro-metering from the x402 gateway. the python client groups the same addresses on a meshslaconfig rather than on the client itself, and its key manager is constructed from a private key hex: the budget ceiling is not a client setting in either runtime. it is a field of the intent mandate ( maxbudgetpaise ), signed by the human principal — see section 6 — so the limit travels with the authorization instead of living in the agent's own configuration, where the agent could change it. ---"
  },
  {
    "route": "/docs/buyer-sdk#3-the-ap2-mandate-chain-inv-02",
    "docTitle": "AI Buyer Agent SDK & AP2 Protocol Guide",
    "headingText": "3. The AP2 Mandate Chain (INV-02)",
    "snippet": "Every transaction executes across a cryptographic mandate chain: ---",
    "searchText": "3. the ap2 mandate chain (inv-02) ai buyer agent sdk & ap2 protocol guide every transaction executes across a cryptographic mandate chain: ---"
  },
  {
    "route": "/docs/buyer-sdk#4-live-sku-quotes--discount-stacking",
    "docTitle": "AI Buyer Agent SDK & AP2 Protocol Guide",
    "headingText": "4. Live SKU Quotes & Discount Stacking",
    "snippet": "A quote prices one SKU at one quantity for one delivery pincode, with the discount tiers already stacked and the GST already split. The quoteHash it returns is...",
    "searchText": "4. live sku quotes & discount stacking ai buyer agent sdk & ap2 protocol guide a quote prices one sku at one quantity for one delivery pincode, with the discount tiers already stacked and the gst already split. the quotehash it returns is what the inventory lock in section 8 is bound to. verifyshippingsla is typescript-only; from python, call the sla route on the mcp server directly. the casing split is not arbitrary. python transport models are snake case because they follow the mcp tool schema, while mandate models are camelcase in both languages because field names are inside the bytes that get signed -- see section 10 before renaming anything. ---"
  },
  {
    "route": "/docs/buyer-sdk#5-bilateral-negotiation-bounds--amendment-mandates-inv-06",
    "docTitle": "AI Buyer Agent SDK & AP2 Protocol Guide",
    "headingText": "5. Bilateral Negotiation Bounds & Amendment Mandates (INV-06)",
    "snippet": "Negotiation is bounded by construction rather than by convention: the SDK ships the turn ceiling and the per-turn micro-fee as constants, so a client cannot...",
    "searchText": "5. bilateral negotiation bounds & amendment mandates (inv-06) ai buyer agent sdk & ap2 protocol guide negotiation is bounded by construction rather than by convention: the sdk ships the turn ceiling and the per-turn micro-fee as constants, so a client cannot quietly bargain forever. a concession arrives as a price-drop alert. applying one produces a dual-signed amendment mandate rather than mutating the cart, which is what keeps concessions monotonic: the amendment records the previous cart's hash and a signed pricedeltapaise , so a later round cannot walk the price back up without leaving a broken chain behind it. the python client's handlepricedropalert is a different method with the same name: it registers an alert with the mcp server and returns the registration, and registerpricedropalert is an alias for it. amendment mandates are constructed there with createsignedamendmentmandate . ---"
  },
  {
    "route": "/docs/buyer-sdk#6-signing-the-mandate-chain",
    "docTitle": "AI Buyer Agent SDK & AP2 Protocol Guide",
    "headingText": "6. Signing the Mandate Chain",
    "snippet": "The buyer agent signs exactly one link of the chain: the Execution Mandate. The Intent Mandate is signed by the human principal's key and the Cart Mandate by...",
    "searchText": "6. signing the mandate chain ai buyer agent sdk & ap2 protocol guide the buyer agent signs exactly one link of the chain: the execution mandate. the intent mandate is signed by the human principal's key and the cart mandate by the merchant's, which is why each helper takes its signer as a separate argument rather than reading one off the client. the three snippets below are not written out here. they are regions of examples/typescript/mandatechain.ts and examples/python/mandatechain.py , two standalone programs that ci compiles and then runs on every push. neither touches the network — signing and hash-chaining are local ed25519 operations — so the whole of inv-02 is exercised without a single service running, and this page cannot drift from code that is proven to work. the intent mandate carries the budget ceiling, signed by the human principal. the limit travels with the authorization rather than living in the agent's own configuration, where the agent could change it. the python helper takes the same fields as flat keyword arguments and the signer as userkeymanager , where typescript takes a params object and a positional signer. the cart mandate arrives over the wire from the merchant enclave; the buyer agent verifies it rather than producing one. it is shown here because the example has to build one to have a chain to verify, and because it is where the gst split is fixed — equal cgstpaise and sgstpaise when the merchant and the buyer are in the same state, the whole amount in igstpaise when they are not. then the one link the buyer agent signs: createsignedexecutionmandate records the sha-256 of each preceding mandate in intentmandatehash and cartmandatehash . that is what makes the chain verifiable rather than merely signed: a cart edited after the user authorized it no longer hashes to the value the execution mandate was signed over, and recomputation catches it without needing to have seen the original. ---"
  },
  {
    "route": "/docs/buyer-sdk#7-verifying-the-chain",
    "docTitle": "AI Buyer Agent SDK & AP2 Protocol Guide",
    "headingText": "7. Verifying the Chain",
    "snippet": "Verification recomputes both hashes and compares them with what the execution mandate recorded. The examples do it twice — once on the chain as signed, once on...",
    "searchText": "7. verifying the chain ai buyer agent sdk & ap2 protocol guide verification recomputes both hashes and compares them with what the execution mandate recorded. the examples do it twice — once on the chain as signed, once on a cart discounted after the fact — and exit non-zero if the second one ever passes. this is the part worth reading twice, because the two runtimes do not have the same contract here: typescript's verifymandatechain is declared = boolean but only ever returns true or throws mandateverificationerror ; it never returns false . so if (!verifymandatechain(...)) compiles, type-checks, and silently never runs its else branch — catch the error instead of testing the result. python's verifymandatehashchain takes raiseonmismatch , which defaults to true but can be set to false for a genuine boolean. running either program prints the two hashes, then verified and rejected , and exits non-zero if that ever inverts: ---"
  },
  {
    "route": "/docs/buyer-sdk#8-atomic-inventory-reservation--fencing-tokens-inv-07",
    "docTitle": "AI Buyer Agent SDK & AP2 Protocol Guide",
    "headingText": "8. Atomic Inventory Reservation & Fencing Tokens (INV-07)",
    "snippet": "Reserve stock against the quote, with a monotonic fencing token so a lock that expired mid-flight cannot be used to settle later: The lock route is metered...",
    "searchText": "8. atomic inventory reservation & fencing tokens (inv-07) ai buyer agent sdk & ap2 protocol guide reserve stock against the quote, with a monotonic fencing token so a lock that expired mid-flight cannot be used to settle later: the lock route is metered under http 402. both clients solve the proof-of-work challenge for you — the python client only while autosolvepow is left on in meshslaconfig . both clients solve the challenge transparently; the python client only while autosolvepow is left on in meshslaconfig . ---"
  },
  {
    "route": "/docs/buyer-sdk#9-ap2-two-phase-commit-settlement-saga-execution",
    "docTitle": "AI Buyer Agent SDK & AP2 Protocol Guide",
    "headingText": "9. AP2 Two-Phase Commit Settlement Saga Execution",
    "snippet": "Submit the whole mandate chain to the Mandate Engine for the 3-way split transfer. This is the final step of the happyPath scenario, described below by the...",
    "searchText": "9. ap2 two-phase commit settlement saga execution ai buyer agent sdk & ap2 protocol guide submit the whole mandate chain to the mandate engine for the 3-way split transfer. this is the final step of the happypath scenario, described below by the driver that runs it: the typescript client also exposes executeautonomouspurchase , which takes the same mandates plus a skuid and quantity and runs quote, lock and settlement as one call. it is the convenience path; the sections above are what it does internally, and are what you want when a step needs to be inspected or retried on its own. ---"
  },
  {
    "route": "/docs/buyer-sdk#10-where-the-two-runtimes-diverge",
    "docTitle": "AI Buyer Agent SDK & AP2 Protocol Guide",
    "headingText": "10. Where the Two Runtimes Diverge",
    "snippet": "The two SDKs are not mirror images, and pretending otherwise is how people write code that typechecks and then fails in production. The divergences fall into...",
    "searchText": "10. where the two runtimes diverge ai buyer agent sdk & ap2 protocol guide the two sdks are not mirror images, and pretending otherwise is how people write code that typechecks and then fails in production. the divergences fall into three groups, and only the first is deliberate."
  },
  {
    "route": "/docs/buyer-sdk#field-casing-and-the-one-rule-you-must-not-clean-up",
    "docTitle": "AI Buyer Agent SDK & AP2 Protocol Guide",
    "headingText": "Field casing, and the one rule you must not \"clean up\"",
    "snippet": "Mandate models are camelCase in both languages, and that is load-bearing. Signing canonicalizes the mandate to JCS — keys sorted, then serialized whole — so...",
    "searchText": "field casing, and the one rule you must not \"clean up\" ai buyer agent sdk & ap2 protocol guide mandate models are camelcase in both languages, and that is load-bearing. signing canonicalizes the mandate to jcs — keys sorted, then serialized whole — so the field names are inside the bytes that get hashed and signed ( jcscanonicalizer.ts , agentkeymanager.canonicalizejson ). rename maxbudgetpaise to max budget paise on the python side and the canonical json changes, the sha-256 changes, and intentmandatehash computed in python stops matching the one computed in typescript. cross-language chain verification breaks silently — the code still runs, the signature still validates locally, and only a mixed-language settlement fails. so: mandatemodels.py is camelcase on purpose. leave it. transport models are the opposite, and they have to face both ways. the mcp tool layer speaks snake case; the mcp http face the sdks actually call speaks camelcase, converting in wiremappers.tosdkskuquote . so transportmodels.py keeps snake case field names and carries a to camel alias generator with populate by name , which lets it parse the camelcase wire while quote.quote hash keeps working. nothing here is canonicalized or signed, so the dual spelling costs nothing but the surprise."
  },
  {
    "route": "/docs/buyer-sdk#names-that-mean-the-same-thing",
    "docTitle": "AI Buyer Agent SDK & AP2 Protocol Guide",
    "headingText": "Names that mean the same thing",
    "snippet": "Neither spelling is more correct; they are accidents of two codebases growing in parallel. Renaming either side is a breaking change for anyone already on it,...",
    "searchText": "names that mean the same thing ai buyer agent sdk & ap2 protocol guide neither spelling is more correct; they are accidents of two codebases growing in parallel. renaming either side is a breaking change for anyone already on it, so they are recorded instead: typescript python what it is --- --- --- getbuyerkeymanager getkeymanager the client's own signer agentkeymanager.fromsecretkey agentkeymanager.fromprivatekeyhex construct from a key getsecretkeyhex getprivatekeyhex read the key back verifymandatechain verifymandatehashchain check the chain (see section 7 — the contracts differ too) solvepowchallenge solvepowchallenge solve the http 402 challenge verifypowsolution verifypowsolution check a solution formatagentdid formatdid render a did:agent: string generateagentkeypair generatekeypair fresh ed25519 pair agentkeypair agentkeypair the pair itself cartitem / taxbreakdown cartitemschema / taxbreakdownschema cart line and tax split mandateverificationerror mandatevalidationerror raised on a broken chain python additionally exports an exception alias beside most error names; they are the same class."
  },
  {
    "route": "/docs/buyer-sdk#capabilities-only-one-side-has",
    "docTitle": "AI Buyer Agent SDK & AP2 Protocol Guide",
    "headingText": "Capabilities only one side has",
    "snippet": "verifyShippingSla is TypeScript-only — from Python, call the SLA route on the MCP server directly. Python has AgentMandateBuilder , PowSolver and...",
    "searchText": "capabilities only one side has ai buyer agent sdk & ap2 protocol guide verifyshippingsla is typescript-only — from python, call the sla route on the mcp server directly. python has agentmandatebuilder , powsolver and validatemandateinvariants with no typescript equivalent, and models the x402 escrow flow ( escrowsession , escrowrefundreceipt ) that typescript does not expose."
  },
  {
    "route": "/docs/buyer-sdk#the-routes-both-clients-call",
    "docTitle": "AI Buyer Agent SDK & AP2 Protocol Guide",
    "headingText": "The routes both clients call",
    "snippet": "Both SDKs now target the same four MCP routes: /api/v1/quote , /api/v1/lock , /api/v1/sla and /api/v1/settlement/execute . That is worth stating because it was...",
    "searchText": "the routes both clients call ai buyer agent sdk & ap2 protocol guide both sdks now target the same four mcp routes: /api/v1/quote , /api/v1/lock , /api/v1/sla and /api/v1/settlement/execute . that is worth stating because it was not true until recently. the python client asked for /api/v1/quotes/live and /api/v1/inventory/lock , which nothing served, and posted the quote where the adapter expects a get . every such call failed against a running mesh while the sdk's own suite stayed green, because it mocks the transport, and its test asserted the wrong path as though that were the contract. test/sdkendpointparity.test.ts in the dashboard now compares every endpoint constant in both sdks against the routes the servers declare, reading both sides from source and mocking nothing."
  },
  {
    "route": "/docs/buyer-sdk#defaults-that-match",
    "docTitle": "AI Buyer Agent SDK & AP2 Protocol Guide",
    "headingText": "Defaults that match",
    "snippet": "Both SDKs share defaultLockTtlSeconds = 60 , matching the MCP server's own default ( packages/mcpServer/src/constants/protocolConstants.ts:53 ). This is the...",
    "searchText": "defaults that match ai buyer agent sdk & ap2 protocol guide both sdks share defaultlockttlseconds = 60 , matching the mcp server's own default ( packages/mcpserver/src/constants/protocolconstants.ts:53 ). this is the hold window for inventory locks; both sdks call the same /api/v1/lock endpoint, so the duration must agree."
  },
  {
    "route": "/docs/merchant-guide",
    "docTitle": "Merchant Onboarding & Universal SKU Studio Guide",
    "headingText": "",
    "snippet": "A comprehensive guide for merchants and enterprise catalog providers registering Ed25519 DIDs, configuring dynamic bullion formulas, defining volume discount...",
    "searchText": " merchant onboarding & universal sku studio guide a comprehensive guide for merchants and enterprise catalog providers registering ed25519 dids, configuring dynamic bullion formulas, defining volume discount tiers, and automating statutory gstr-1 tax compliance. ---"
  },
  {
    "route": "/docs/merchant-guide#1-merchant-identity--did-derivation",
    "docTitle": "Merchant Onboarding & Universal SKU Studio Guide",
    "headingText": "1. Merchant Identity & DID Derivation",
    "snippet": "Every merchant on RazorAgent Mesh is identified by an immutable Decentralized Identifier ( did:razoragent:merchant: ) derived from an Ed25519 cryptographic...",
    "searchText": "1. merchant identity & did derivation merchant onboarding & universal sku studio guide every merchant on razoragent mesh is identified by an immutable decentralized identifier ( did:razoragent:merchant: ) derived from an ed25519 cryptographic public key."
  },
  {
    "route": "/docs/merchant-guide#verification--validation-rules",
    "docTitle": "Merchant Onboarding & Universal SKU Studio Guide",
    "headingText": "Verification & Validation Rules",
    "snippet": "- Luhn Mod-36 GSTIN Check : The 15-character Indian GSTIN is verified using the statutory Luhn Mod-36 checksum algorithm. - Razorpay Route Account : Linked...",
    "searchText": "verification & validation rules merchant onboarding & universal sku studio guide - luhn mod-36 gstin check : the 15-character indian gstin is verified using the statutory luhn mod-36 checksum algorithm. - razorpay route account : linked accounts must match the pattern acc [a-za-z0-9]+ for automated 2pc split transfers. ---"
  },
  {
    "route": "/docs/merchant-guide#2-multi-channel-catalog-ingestion",
    "docTitle": "Merchant Onboarding & Universal SKU Studio Guide",
    "headingText": "2. Multi-Channel Catalog Ingestion",
    "snippet": "RazorAgent Mesh supports 4 ingestion adapters for populating and vectorizing merchant catalogs: The single-SKU route is abbreviated above to fit the diagram....",
    "searchText": "2. multi-channel catalog ingestion merchant onboarding & universal sku studio guide razoragent mesh supports 4 ingestion adapters for populating and vectorizing merchant catalogs: the single-sku route is abbreviated above to fit the diagram. in full it is post /api/v1/merchant/{merchantdid}/catalog -- the merchant did is part of the path, not a header, so a catalog write is always scoped to one merchant."
  },
  {
    "route": "/docs/merchant-guide#multi-tier-volume-discount-configuration",
    "docTitle": "Merchant Onboarding & Universal SKU Studio Guide",
    "headingText": "Multi-Tier Volume Discount Configuration",
    "snippet": "Merchants can define tiered volume discount curves in Basis Points (1 BPS = 0.01%): ---",
    "searchText": "multi-tier volume discount configuration merchant onboarding & universal sku studio guide merchants can define tiered volume discount curves in basis points (1 bps = 0.01%): ---"
  },
  {
    "route": "/docs/merchant-guide#3-dynamic-bullion-spot-pricing-inv-05",
    "docTitle": "Merchant Onboarding & Universal SKU Studio Guide",
    "headingText": "3. Dynamic Bullion Spot Pricing (INV-05)",
    "snippet": "For gold and silver precious metals, pricing is calculated dynamically from the live MCX Spot Oracle with a 5-second cache: Bullion Spot Formula:...",
    "searchText": "3. dynamic bullion spot pricing (inv-05) merchant onboarding & universal sku studio guide for gold and silver precious metals, pricing is calculated dynamically from the live mcx spot oracle with a 5-second cache: bullion spot formula: unitpricepaise = ⌊(spotpergrampaise × puritycarats) / 24⌋ × weightgrams + makingchargespaise ---"
  },
  {
    "route": "/docs/merchant-guide#4-vertical-domain-facet-schema",
    "docTitle": "Merchant Onboarding & Universal SKU Studio Guide",
    "headingText": "4. Vertical Domain Facet Schema",
    "snippet": "Catalogs support specialized industry facets with custom attribute normalization: Industry Domain Key Schema Attributes Example Payload --- --- --- Jewelry...",
    "searchText": "4. vertical domain facet schema merchant onboarding & universal sku studio guide catalogs support specialized industry facets with custom attribute normalization: industry domain key schema attributes example payload --- --- --- jewelry purity ( 18k / 22k / 24k ), weight (g), making charges {\"purity\": \"22k\", \"weightgrams\": 10.5} apparel size ( s / m / l / xl ), color, fabric, gsm {\"size\": \"l\", \"fabric\": \"cotton\", \"gsm\": 220} pharma active molecule, schedule class, expiry batch {\"molecule\": \"paracetamol\", \"dosage\": \"650mg\"} fmcg net weight, shelf life, organic certification {\"shelflifedays\": 180, \"organic\": true} ---"
  },
  {
    "route": "/docs/merchant-guide#5-statutory-hsn-chapter-resolution--tax-rules-inv-04",
    "docTitle": "Merchant Onboarding & Universal SKU Studio Guide",
    "headingText": "5. Statutory HSN Chapter Resolution & Tax Rules (INV-04)",
    "snippet": "Every SKU maps to an official Indian Harmonized System of Nomenclature (HSN) chapter: HSN Code Chapter Category GST Rate Statutory Split --- --- --- --- 7113...",
    "searchText": "5. statutory hsn chapter resolution & tax rules (inv-04) merchant onboarding & universal sku studio guide every sku maps to an official indian harmonized system of nomenclature (hsn) chapter: hsn code chapter category gst rate statutory split --- --- --- --- 7113 gold & precious jewelry 3.0% 1.5% cgst + 1.5% sgst (or 3.0% igst) 6109 cotton & knitted apparel 5.0% 2.5% cgst + 2.5% sgst (or 5.0% igst) 3004 essential pharmaceuticals 5.0% 2.5% cgst + 2.5% sgst (or 5.0% igst) 8471 computing & electronics 18.0% 9.0% cgst + 9.0% sgst (or 18.0% igst)"
  },
  {
    "route": "/docs/telemetry",
    "docTitle": "RazorAgent Mesh v2.0 — Real-Time Telemetry & Event Streaming Specification",
    "headingText": "",
    "snippet": "---",
    "searchText": " razoragent mesh v2.0 — real-time telemetry & event streaming specification ---"
  },
  {
    "route": "/docs/telemetry#1-real-time-telemetry-architecture",
    "docTitle": "RazorAgent Mesh v2.0 — Real-Time Telemetry & Event Streaming Specification",
    "headingText": "1. Real-Time Telemetry Architecture",
    "snippet": "The RazorAgent Mesh v2.0 telemetry pipeline provides a high-throughput, low-latency asynchronous event streaming backbone for autonomous multi-agent commerce....",
    "searchText": "1. real-time telemetry architecture razoragent mesh v2.0 — real-time telemetry & event streaming specification the razoragent mesh v2.0 telemetry pipeline provides a high-throughput, low-latency asynchronous event streaming backbone for autonomous multi-agent commerce. it captures the entire lifecycle of multi-agent interactions across all protocol layers—including model context protocol (mcp) json-rpc execution, rubinstein-ståhl bilateral bargaining concessions, sub-300ms vector semantic self-healing, ap2 cryptographic mandate signing, and 2-phase commit (2pc) multi-party settlements."
  },
  {
    "route": "/docs/telemetry#11-asynchronous-pub-sub-architecture",
    "docTitle": "RazorAgent Mesh v2.0 — Real-Time Telemetry & Event Streaming Specification",
    "headingText": "1.1 Asynchronous Pub-Sub Architecture",
    "snippet": "The telemetry pipeline operates on an asynchronous Server-Sent Events (SSE) publish-subscribe model implemented via Python's asyncio primitives in...",
    "searchText": "1.1 asynchronous pub-sub architecture razoragent mesh v2.0 — real-time telemetry & event streaming specification the telemetry pipeline operates on an asynchronous server-sent events (sse) publish-subscribe model implemented via python's asyncio primitives in mandateengine/telemetryemitter.py ."
  },
  {
    "route": "/docs/telemetry#12-core-operational--architectural-invariants",
    "docTitle": "RazorAgent Mesh v2.0 — Real-Time Telemetry & Event Streaming Specification",
    "headingText": "1.2 Core Operational & Architectural Invariants",
    "snippet": "1. Subscriber Queue Isolation & Capacity: Every connected listener receives a dedicated asyncio.Queue[str] configured with a capacity of 500 event frames (...",
    "searchText": "1.2 core operational & architectural invariants razoragent mesh v2.0 — real-time telemetry & event streaming specification 1. subscriber queue isolation & capacity: every connected listener receives a dedicated asyncio.queue[str] configured with a capacity of 500 event frames ( defaultqueuecapacity = 500 ). 2. non-blocking ingestion & backpressure handling: event publishing executes via put nowait() . if a client queue saturates because of slow network consumption, the server drops the stale queue rather than blocking the producer pipeline, preventing memory leakage and system degradation. 3. heartbeat keep-alive frame: when no event traffic occurs within 15 seconds ( heartbeatintervalseconds = 15 ), the server emits an sse comment heartbeat frame ( : heartbeat\\n\\n ) to preserve tcp socket persistence across load balancers, nat gateways, and reverse proxies. 4. resilient client auto-reconnection: client consumers implement exponential backoff reconnection logic: reconnection allows client consumers to recover automatically from transient socket resets without data loss. 5. thread-safe mutex lock: registration, unregistration, and broadcast dispatch across active subscriber queues are guarded by asyncio.lock() . ---"
  },
  {
    "route": "/docs/telemetry#2-server-sent-events-sse-streaming-api-reference",
    "docTitle": "RazorAgent Mesh v2.0 — Real-Time Telemetry & Event Streaming Specification",
    "headingText": "2. Server-Sent Events (SSE) Streaming API Reference",
    "snippet": "",
    "searchText": "2. server-sent events (sse) streaming api reference razoragent mesh v2.0 — real-time telemetry & event streaming specification "
  },
  {
    "route": "/docs/telemetry#21-live-event-stream-endpoint-get-apiv1telemetrystream",
    "docTitle": "RazorAgent Mesh v2.0 — Real-Time Telemetry & Event Streaming Specification",
    "headingText": "2.1 Live Event Stream Endpoint (GET /api/v1/telemetry/stream)",
    "snippet": "Subscribes an HTTP client to the live telemetry event stream using standard HTTP/1.1 or HTTP/2 Server-Sent Events. Response Headers SSE Wire Format Telemetry...",
    "searchText": "2.1 live event stream endpoint (get /api/v1/telemetry/stream) razoragent mesh v2.0 — real-time telemetry & event streaming specification subscribes an http client to the live telemetry event stream using standard http/1.1 or http/2 server-sent events. response headers sse wire format telemetry events are serialized to json with compact key-value separators ( , , : ) and prefixed with data: and terminated by \\n\\n : ---"
  },
  {
    "route": "/docs/telemetry#22-telemetry-event-ingestion-post-apiv1telemetryevents",
    "docTitle": "RazorAgent Mesh v2.0 — Real-Time Telemetry & Event Streaming Specification",
    "headingText": "2.2 Telemetry Event Ingestion (POST /api/v1/telemetry/events)",
    "snippet": "Allows internal microservices, external agent gateways, or testing harnesses to ingest telemetry frames into the broadcast queue. Response (HTTP 200 OK) ---",
    "searchText": "2.2 telemetry event ingestion (post /api/v1/telemetry/events) razoragent mesh v2.0 — real-time telemetry & event streaming specification allows internal microservices, external agent gateways, or testing harnesses to ingest telemetry frames into the broadcast queue. response (http 200 ok) ---"
  },
  {
    "route": "/docs/telemetry#23-health--liveness-verification-endpoint-get-health",
    "docTitle": "RazorAgent Mesh v2.0 — Real-Time Telemetry & Event Streaming Specification",
    "headingText": "2.3 Health & Liveness Verification Endpoint (GET /health)",
    "snippet": "Returns real-time service health status, active SSE subscriber counts, and subsystem connection readiness. Response (HTTP 200 OK) ---",
    "searchText": "2.3 health & liveness verification endpoint (get /health) razoragent mesh v2.0 — real-time telemetry & event streaming specification returns real-time service health status, active sse subscriber counts, and subsystem connection readiness. response (http 200 ok) ---"
  },
  {
    "route": "/docs/telemetry#24-command-line-telemetry-stream-inspection",
    "docTitle": "RazorAgent Mesh v2.0 — Real-Time Telemetry & Event Streaming Specification",
    "headingText": "2.4 Command-Line Telemetry Stream Inspection",
    "snippet": "Developers and infrastructure engineers can consume and inspect the unbuffered live SSE feed directly from the command line using curl : Python client...",
    "searchText": "2.4 command-line telemetry stream inspection razoragent mesh v2.0 — real-time telemetry & event streaming specification developers and infrastructure engineers can consume and inspect the unbuffered live sse feed directly from the command line using curl : python client consumption script: ---"
  },
  {
    "route": "/docs/telemetry#3-canonical-event-schema-specifications",
    "docTitle": "RazorAgent Mesh v2.0 — Real-Time Telemetry & Event Streaming Specification",
    "headingText": "3. Canonical Event Schema Specifications",
    "snippet": "All telemetry events extend the base immutable envelope BaseTelemetryEvent and map directly to Pydantic models on the backend and TypeScript interfaces on the...",
    "searchText": "3. canonical event schema specifications razoragent mesh v2.0 — real-time telemetry & event streaming specification all telemetry events extend the base immutable envelope basetelemetryevent and map directly to pydantic models on the backend and typescript interfaces on the client. the table below is not written here -- it is read from the telemetryeventtype union and the badge map at build time, so it cannot fall behind the code the way a hand-counted list does. ---"
  },
  {
    "route": "/docs/telemetry#1-mcp_tool_call",
    "docTitle": "RazorAgent Mesh v2.0 — Real-Time Telemetry & Event Streaming Specification",
    "headingText": "1. MCP_TOOL_CALL",
    "snippet": "Emitted when an autonomous AI buyer agent invokes any of the eight merchant Model Context Protocol (MCP) JSON-RPC tools: search catalog , get live sku quote ,...",
    "searchText": "1. mcp_tool_call razoragent mesh v2.0 — real-time telemetry & event streaming specification emitted when an autonomous ai buyer agent invokes any of the eight merchant model context protocol (mcp) json-rpc tools: search catalog , get live sku quote , reserve inventory lock , verify shipping sla , establish agent delegation , create cart mandate , sign execution mandate and execute settlement . typescript schema json payload ---"
  },
  {
    "route": "/docs/telemetry#2-mcp_tool_result",
    "docTitle": "RazorAgent Mesh v2.0 — Real-Time Telemetry & Event Streaming Specification",
    "headingText": "2. MCP_TOOL_RESULT",
    "snippet": "Emitted upon completion of an MCP tool invocation, reporting the execution status, output data, and exact latency in milliseconds ( durationMs ). TypeScript...",
    "searchText": "2. mcp_tool_result razoragent mesh v2.0 — real-time telemetry & event streaming specification emitted upon completion of an mcp tool invocation, reporting the execution status, output data, and exact latency in milliseconds ( durationms ). typescript schema json payload ---"
  },
  {
    "route": "/docs/telemetry#3-bid_turn_completed",
    "docTitle": "RazorAgent Mesh v2.0 — Real-Time Telemetry & Event Streaming Specification",
    "headingText": "3. BID_TURN_COMPLETED",
    "snippet": "Emitted after each Rubinstein-Ståhl bargaining turn, capturing the buyer's bid, the seller's ask, the spread in paise, and the anti-spam micro-escrow fee burn...",
    "searchText": "3. bid_turn_completed razoragent mesh v2.0 — real-time telemetry & event streaming specification emitted after each rubinstein-ståhl bargaining turn, capturing the buyer's bid, the seller's ask, the spread in paise, and the anti-spam micro-escrow fee burn (50 paise/turn). typescript schema json payload ---"
  },
  {
    "route": "/docs/telemetry#4-negotiation_converged",
    "docTitle": "RazorAgent Mesh v2.0 — Real-Time Telemetry & Event Streaming Specification",
    "headingText": "4. NEGOTIATION_CONVERGED",
    "snippet": "Emitted when the buyer bid and seller ask reach mathematical equilibrium , binding the agreed unit price and compiling the RFC 8785 Abstract Syntax Tree (AST)...",
    "searchText": "4. negotiation_converged razoragent mesh v2.0 — real-time telemetry & event streaming specification emitted when the buyer bid and seller ask reach mathematical equilibrium , binding the agreed unit price and compiling the rfc 8785 abstract syntax tree (ast) contract hash. typescript schema json payload ---"
  },
  {
    "route": "/docs/telemetry#5-mandate_signed",
    "docTitle": "RazorAgent Mesh v2.0 — Real-Time Telemetry & Event Streaming Specification",
    "headingText": "5. MANDATE_SIGNED",
    "snippet": "Emitted during each step of the 4-phase AP2 mandate chain lifecycle ( ), broadcasting non-repudiable Ed25519 signatures, RFC 8785 Canonical JSON previews, and...",
    "searchText": "5. mandate_signed razoragent mesh v2.0 — real-time telemetry & event streaming specification emitted during each step of the 4-phase ap2 mandate chain lifecycle ( ), broadcasting non-repudiable ed25519 signatures, rfc 8785 canonical json previews, and hash bindings. typescript schema json payload ---"
  },
  {
    "route": "/docs/telemetry#6-payment_captured",
    "docTitle": "RazorAgent Mesh v2.0 — Real-Time Telemetry & Event Streaming Specification",
    "headingText": "6. PAYMENT_CAPTURED",
    "snippet": "Emitted when 2-Phase Commit (2PC) settlement executes across Razorpay Route accounts, logging the 3-way conserved split transfers and the statutory GSTR-1...",
    "searchText": "6. payment_captured razoragent mesh v2.0 — real-time telemetry & event streaming specification emitted when 2-phase commit (2pc) settlement executes across razorpay route accounts, logging the 3-way conserved split transfers and the statutory gstr-1 sha-256 tax hash. typescript schema json payload ---"
  },
  {
    "route": "/docs/telemetry#7-oos_healed",
    "docTitle": "RazorAgent Mesh v2.0 — Real-Time Telemetry & Event Streaming Specification",
    "headingText": "7. OOS_HEALED",
    "snippet": "Emitted when the Vector Healer intercepts an out-of-stock SKU and executes an Approximate Nearest Neighbor (ANN) substitution in Qdrant within the sub-300ms...",
    "searchText": "7. oos_healed razoragent mesh v2.0 — real-time telemetry & event streaming specification emitted when the vector healer intercepts an out-of-stock sku and executes an approximate nearest neighbor (ann) substitution in qdrant within the sub-300ms sla. typescript schema json payload ---"
  },
  {
    "route": "/docs/telemetry#8-budget_blocked",
    "docTitle": "RazorAgent Mesh v2.0 — Real-Time Telemetry & Event Streaming Specification",
    "headingText": "8. BUDGET_BLOCKED",
    "snippet": "Emitted when an autonomous cart or execution mandate attempts to exceed the user's delegated spending cap, triggering a deterministic block with 0 external API...",
    "searchText": "8. budget_blocked razoragent mesh v2.0 — real-time telemetry & event streaming specification emitted when an autonomous cart or execution mandate attempts to exceed the user's delegated spending cap, triggering a deterministic block with 0 external api calls made. typescript schema json payload ---"
  },
  {
    "route": "/docs/telemetry#9-pow_challenge_solved",
    "docTitle": "RazorAgent Mesh v2.0 — Real-Time Telemetry & Event Streaming Specification",
    "headingText": "9. POW_CHALLENGE_SOLVED",
    "snippet": "Emitted upon verification of an ingress SHA-256 Proof-of-Work challenge, proving computational commitment to mitigate Sybil attacks and API flooding....",
    "searchText": "9. pow_challenge_solved razoragent mesh v2.0 — real-time telemetry & event streaming specification emitted upon verification of an ingress sha-256 proof-of-work challenge, proving computational commitment to mitigate sybil attacks and api flooding. typescript schema json payload ---"
  },
  {
    "route": "/docs/telemetry#10-inventory_locked",
    "docTitle": "RazorAgent Mesh v2.0 — Real-Time Telemetry & Event Streaming Specification",
    "headingText": "10. INVENTORY_LOCKED",
    "snippet": "Emitted when Redis acquires an atomic inventory reservation lock with a monotonically increasing fencing token and Time-To-Live (TTL). TypeScript Schema JSON...",
    "searchText": "10. inventory_locked razoragent mesh v2.0 — real-time telemetry & event streaming specification emitted when redis acquires an atomic inventory reservation lock with a monotonically increasing fencing token and time-to-live (ttl). typescript schema json payload ---"
  },
  {
    "route": "/docs/telemetry#11-route_rollback_triggered",
    "docTitle": "RazorAgent Mesh v2.0 — Real-Time Telemetry & Event Streaming Specification",
    "headingText": "11. ROUTE_ROLLBACK_TRIGGERED",
    "snippet": "Emitted when a secondary transfer in a 2-Phase Commit settlement fails, triggering LIFO compensation reverse transfers to ensure transactional atomicity....",
    "searchText": "11. route_rollback_triggered razoragent mesh v2.0 — real-time telemetry & event streaming specification emitted when a secondary transfer in a 2-phase commit settlement fails, triggering lifo compensation reverse transfers to ensure transactional atomicity. typescript schema json payload ---"
  },
  {
    "route": "/docs/telemetry#12-heartbeat",
    "docTitle": "RazorAgent Mesh v2.0 — Real-Time Telemetry & Event Streaming Specification",
    "headingText": "12. HEARTBEAT",
    "snippet": "Emitted periodically every 15 seconds to maintain keep-alive persistence on the SSE streaming channel. TypeScript Schema JSON Payload ---",
    "searchText": "12. heartbeat razoragent mesh v2.0 — real-time telemetry & event streaming specification emitted periodically every 15 seconds to maintain keep-alive persistence on the sse streaming channel. typescript schema json payload ---"
  },
  {
    "route": "/docs/telemetry#4-metric-computation-algorithms--mathematical-formulations",
    "docTitle": "RazorAgent Mesh v2.0 — Real-Time Telemetry & Event Streaming Specification",
    "headingText": "4. Metric Computation Algorithms & Mathematical Formulations",
    "snippet": "",
    "searchText": "4. metric computation algorithms & mathematical formulations razoragent mesh v2.0 — real-time telemetry & event streaming specification "
  },
  {
    "route": "/docs/telemetry#41-mathematical-formulations",
    "docTitle": "RazorAgent Mesh v2.0 — Real-Time Telemetry & Event Streaming Specification",
    "headingText": "4.1 Mathematical Formulations",
    "snippet": "Total Settled Volume ( ) Aggregates the total settled transaction value in integer paise across all PAYMENT CAPTURED events: Settlement Success Rate ( )...",
    "searchText": "4.1 mathematical formulations razoragent mesh v2.0 — real-time telemetry & event streaming specification total settled volume ( ) aggregates the total settled transaction value in integer paise across all payment captured events: settlement success rate ( ) measures the reliability of 2pc multi-party transfers: negotiation convergence rate ( ) quantifies the efficiency of bilateral rubinstein-ståhl bargaining turns reaching equilibrium within the maximum turn boundary ( ): average vector healing latency ( ) calculates the mean duration in milliseconds for the vector healer to resolve an out-of-stock exception via qdrant cosine similarity search: self-healing sla pass rate ( ) measures the percentage of vector substitutions that both complete under the 300ms deadline and satisfy 100% of negative constraints: micro-escrow anti-spam fee accumulation calculates the total non-refundable anti-spam burn collected across all completed bargaining turns: conserved route settlement invariant (inv-04) ensures zero-loss conservation of funds across multi-party split transfers: ---"
  },
  {
    "route": "/docs/telemetry#5-verification--testing-reference",
    "docTitle": "RazorAgent Mesh v2.0 — Real-Time Telemetry & Event Streaming Specification",
    "headingText": "5. Verification & Testing Reference",
    "snippet": "Run the dedicated test suite verifying the telemetry emitter, SSE streaming async generator, subscriber queue management, and payload serialization:",
    "searchText": "5. verification & testing reference razoragent mesh v2.0 — real-time telemetry & event streaming specification run the dedicated test suite verifying the telemetry emitter, sse streaming async generator, subscriber queue management, and payload serialization:"
  },
  {
    "route": "/docs/gstr1-invoice",
    "docTitle": "Statutory GSTR-1 Tax Invoice Specification & Deterministic Integer Tax Engine",
    "headingText": "",
    "snippet": "---",
    "searchText": " statutory gstr-1 tax invoice specification & deterministic integer tax engine ---"
  },
  {
    "route": "/docs/gstr1-invoice#1-regulatory-invoicing-mandate--statutory-framework",
    "docTitle": "Statutory GSTR-1 Tax Invoice Specification & Deterministic Integer Tax Engine",
    "headingText": "1. Regulatory Invoicing Mandate & Statutory Framework",
    "snippet": "Under the Indian Goods and Services Tax (GST) regime, autonomous multi-agent commerce must produce non-repudiable, statutory tax invoices that comply with all...",
    "searchText": "1. regulatory invoicing mandate & statutory framework statutory gstr-1 tax invoice specification & deterministic integer tax engine under the indian goods and services tax (gst) regime, autonomous multi-agent commerce must produce non-repudiable, statutory tax invoices that comply with all applicable legal standards governing electronic invoicing and digital marketplace transactions."
  },
  {
    "route": "/docs/gstr1-invoice#11-statutory-legal-basis",
    "docTitle": "Statutory GSTR-1 Tax Invoice Specification & Deterministic Integer Tax Engine",
    "headingText": "1.1 Statutory Legal Basis",
    "snippet": "1. Section 31 of Central Goods and Services Tax (CGST) Act, 2017: Mandates that every registered taxable person supplying taxable goods or services must issue...",
    "searchText": "1.1 statutory legal basis statutory gstr-1 tax invoice specification & deterministic integer tax engine 1. section 31 of central goods and services tax (cgst) act, 2017: mandates that every registered taxable person supplying taxable goods or services must issue a tax invoice showing the description, quantity, value of goods, tax charged thereon, and other prescribed particulars. 2. rule 46 of cgst rules, 2017 (mandatory invoice particulars): requires sixteen essential particulars on every tax invoice, including: - name, address, and goods and services tax identification number ( gstin ) of the supplier. - a consecutive serial number not exceeding 16 characters containing alphabets, numerals, and special characters. - date of invoice issuance. - name, address, and gstin/unique identification number (uin) of the recipient. - harmonized system of nomenclature ( hsn ) code for goods or accounting code for services. - description of goods or services. - quantity of goods and unit of measurement. - total taxable value of supply of goods or services taking into account any discount or abatement. - rate of tax (central gst, state gst, integrated gst, or cess). - amount of tax charged in respect of taxable goods or services segregated by cgst, sgst, and igst. - place of supply along with the name of the state and its two-digit state code. - digital signature or electronic verification stamp of the supplier or authorized agent. 3. section 52 of cgst act, 2017 (tax collection at source / tcs): mandates that electronic commerce operators (eco) collect tcs at the rate of 1.00% (100 basis points) on the net value of taxable supplies made through the platform: - intra-state supplies: 0.50% cgst (50 bps) + 0.50% sgst (50 bps). - inter-state supplies: 1.00% igst (100 bps). ---"
  },
  {
    "route": "/docs/gstr1-invoice#2-deterministic-integer-paise-tax-engine",
    "docTitle": "Statutory GSTR-1 Tax Invoice Specification & Deterministic Integer Tax Engine",
    "headingText": "2. Deterministic Integer Paise Tax Engine",
    "snippet": "Financial calculations in RazorAgent Mesh are strictly isolated inside the Arithmetic Enclave ( mandateEngine/verification/arithmeticEnclave.py ). This enclave...",
    "searchText": "2. deterministic integer paise tax engine statutory gstr-1 tax invoice specification & deterministic integer tax engine financial calculations in razoragent mesh are strictly isolated inside the arithmetic enclave ( mandateengine/verification/arithmeticenclave.py ). this enclave guarantees mathematical precision and prevents floating-point drift, fractional penny discrepancies, and non-deterministic rounding errors across multi-party settlements."
  },
  {
    "route": "/docs/gstr1-invoice#21-invariant-inv-01-pure-integer-paise-arithmetic",
    "docTitle": "Statutory GSTR-1 Tax Invoice Specification & Deterministic Integer Tax Engine",
    "headingText": "2.1 Invariant INV-01: Pure Integer Paise Arithmetic",
    "snippet": "- All financial values (prices, unit costs, discounts, shipping fees, tax components, and settlement splits) are represented strictly as integer paise ( ). -...",
    "searchText": "2.1 invariant inv-01: pure integer paise arithmetic statutory gstr-1 tax invoice specification & deterministic integer tax engine - all financial values (prices, unit costs, discounts, shipping fees, tax components, and settlement splits) are represented strictly as integer paise ( ). - the use of floating-point types ( float , double ) in any financial calculation path is strictly forbidden and triggers an immediate arithmeticdriftexception ."
  },
  {
    "route": "/docs/gstr1-invoice#22-invariant-inv-02-deterministic-statutory-gst-calculation",
    "docTitle": "Statutory GSTR-1 Tax Invoice Specification & Deterministic Integer Tax Engine",
    "headingText": "2.2 Invariant INV-02: Deterministic Statutory GST Calculation",
    "snippet": "GST is computed independently per itemized line item using statutory floor division. CGST and SGST are two separate levies, each charged at exactly half the...",
    "searchText": "2.2 invariant inv-02: deterministic statutory gst calculation statutory gstr-1 tax invoice specification & deterministic integer tax engine gst is computed independently per itemized line item using statutory floor division. cgst and sgst are two separate levies, each charged at exactly half the combined rate, so both components are computed with the identical expression and are therefore always equal. the line total is defined as their sum, which makes penny conservation structural rather than something a rounding rule has to recover. place of supply classification intra-state formulation (cgst + sgst) for supplies where the merchant and delivery location share the same two-digit gst state code: statutory equality guarantee: cgst and sgst are distinct levies each charged at half the combined rate, so they must be equal , not merely sum to the total. both are computed from the identical expression, which makes that equality hold by construction for every rate — including odd slabs such as 5%, where deriving one component as the remainder of the other would produce an illegal asymmetric split (2% / 3% instead of 2.5% / 2.5%). exact conservation guarantee: because is defined as , the identity holds with zero drift by definition. the single division by (equivalently, by when the rate is expressed in basis points) is deliberate: halving the rate first and then flooring twice would discard up to one paise per line item and put this engine one paise out of step with the typescript mcp quoter. inter-state formulation (igst) for supplies across differing state jurisdictions: ---"
  },
  {
    "route": "/docs/gstr1-invoice#23-section-52-tcs-withholding-formulation",
    "docTitle": "Statutory GSTR-1 Tax Invoice Specification & Deterministic Integer Tax Engine",
    "headingText": "2.3 Section 52 TCS Withholding Formulation",
    "snippet": "Section 52 Tax Collection at Source (TCS) is computed on the net taxable base across the order: Intra-State TCS (100 bps = 50 bps CGST + 50 bps SGST)...",
    "searchText": "2.3 section 52 tcs withholding formulation statutory gstr-1 tax invoice specification & deterministic integer tax engine section 52 tax collection at source (tcs) is computed on the net taxable base across the order: intra-state tcs (100 bps = 50 bps cgst + 50 bps sgst) inter-state tcs (100 bps igst) ---"
  },
  {
    "route": "/docs/gstr1-invoice#24-conserved-global-discount-allocation-largest-remainder-method",
    "docTitle": "Statutory GSTR-1 Tax Invoice Specification & Deterministic Integer Tax Engine",
    "headingText": "2.4 Conserved Global Discount Allocation (Largest Remainder Method)",
    "snippet": "When a global promotional discount ( ) is applied across line items with taxable values (where ), the discount is apportioned using the Hare-Niemeyer (Largest...",
    "searchText": "2.4 conserved global discount allocation (largest remainder method) statutory gstr-1 tax invoice specification & deterministic integer tax engine when a global promotional discount ( ) is applied across line items with taxable values (where ), the discount is apportioned using the hare-niemeyer (largest remainder) algorithm to prevent fractional penny loss: 1. compute base floor allocations: 2. distribute residual paise: the remaining unallocated paise are assigned 1 paise at a time to the items with the largest fractional remainders . 3. conservation invariant: ---"
  },
  {
    "route": "/docs/gstr1-invoice#25-statutory-hsn-tax-slabs",
    "docTitle": "Statutory GSTR-1 Tax Invoice Specification & Deterministic Integer Tax Engine",
    "headingText": "2.5 Statutory HSN Tax Slabs",
    "snippet": "The engine supports all 5 official GST tax rate tiers: Slab Rate (%) Statutory Category Representative HSN Codes --- --- --- --- Exempt 0% Unprocessed...",
    "searchText": "2.5 statutory hsn tax slabs statutory gstr-1 tax invoice specification & deterministic integer tax engine the engine supports all 5 official gst tax rate tiers: slab rate (%) statutory category representative hsn codes --- --- --- --- exempt 0% unprocessed agricultural products, essential food grains, raw milk 0401 (milk), 1001 (wheat) merit / essential 5% life-saving pharmaceuticals, packaged edible oils, economy textiles 3004 (medicaments), 1507 (soya oil) standard-1 12% processed foods, basic electronic components, diagnostic machinery 8418 (refrigerators), 9018 (medical instruments) standard-2 18% general electronics, commercial furniture, industrial capital goods 8504 (transformers), 9401 (furniture) demerit / luxury 28% luxury motor vehicles, premium consumer electronics, aerated drinks 8703 (automobiles), 2202 (beverages) bullion 3% gold 24k/22k coins & bars, silver ingots, jewelry articles 7113 (jewelry), 7108 (gold bullion) ---"
  },
  {
    "route": "/docs/gstr1-invoice#3-print-ready-html-invoice-generator",
    "docTitle": "Statutory GSTR-1 Tax Invoice Specification & Deterministic Integer Tax Engine",
    "headingText": "3. Print-Ready HTML Invoice Generator",
    "snippet": "The HTML generation subsystem ( mandateEngine/tax/gstrInvoiceHtmlRenderer.py ) converts structured GstrInvoicePayload models into self-contained, responsive,...",
    "searchText": "3. print-ready html invoice generator statutory gstr-1 tax invoice specification & deterministic integer tax engine the html generation subsystem ( mandateengine/tax/gstrinvoicehtmlrenderer.py ) converts structured gstrinvoicepayload models into self-contained, responsive, print-ready html documents."
  },
  {
    "route": "/docs/gstr1-invoice#31-document-layout--component-structure",
    "docTitle": "Statutory GSTR-1 Tax Invoice Specification & Deterministic Integer Tax Engine",
    "headingText": "3.1 Document Layout & Component Structure",
    "snippet": "The rendered HTML document contains five distinct sections structured to satisfy Rule 46: 1. Header & Legal Classification Grid ( .header-grid ): - Title: TAX...",
    "searchText": "3.1 document layout & component structure statutory gstr-1 tax invoice specification & deterministic integer tax engine the rendered html document contains five distinct sections structured to satisfy rule 46: 1. header & legal classification grid ( .header-grid ): - title: tax invoice - statutory citation: issued under section 31 of cgst act, 2017 & rule 46 of cgst rules - invoice metadata badge: invoice number, date, supply classification ( intra-state (cgst + sgst) or inter-state (igst) ). 2. entity details grid ( .details-grid ): - seller / supplier box: legal name, 15-character gstin, state name & 2-digit code. - recipient / place of supply box: recipient legal name, place of supply (pos) state & code, protocol identifier ( razoragent mesh v2.0 ). 3. itemized tax breakdown table ( .data-table ): - columns: , sku identifier , hsn , qty , unit price , taxable amt , rate , cgst , sgst , igst , line total . - table footer: sum of taxable subtotal, total cgst, total sgst, total igst, and total invoice value. 4. summary & tcs grid ( .bottom-grid ): - section 52 tcs card: net taxable base, statutory tcs rate (100 bps), and total tcs withheld. - financial summary card: taxable subtotal, total gst, shipping & handling, promotional discount, and grand total. 5. cryptographic audit verification stamp ( .audit-stamp ): - visual verified checkmark badge ( ✓ cryptographic verification & audit stamp ). - 64-character hexadecimal sha-256 digest rendered in a monospace code container. - non-repudiation certification stamp with timestamp. ---"
  },
  {
    "route": "/docs/gstr1-invoice#32-responsive--print-optimized-stylesheet",
    "docTitle": "Statutory GSTR-1 Tax Invoice Specification & Deterministic Integer Tax Engine",
    "headingText": "3.2 Responsive & Print-Optimized Stylesheet",
    "snippet": "The inline stylesheet ( gstrInvoiceHtmlStyles.py ) provides responsive desktop presentation and A4 portrait print styling: ---",
    "searchText": "3.2 responsive & print-optimized stylesheet statutory gstr-1 tax invoice specification & deterministic integer tax engine the inline stylesheet ( gstrinvoicehtmlstyles.py ) provides responsive desktop presentation and a4 portrait print styling: ---"
  },
  {
    "route": "/docs/gstr1-invoice#33-security--xss-sanitization",
    "docTitle": "Statutory GSTR-1 Tax Invoice Specification & Deterministic Integer Tax Engine",
    "headingText": "3.3 Security & XSS Sanitization",
    "snippet": "To prevent Cross-Site Scripting (XSS) or HTML tag breakout from untrusted merchant or product metadata, all dynamic strings (SKU identifiers, product titles,...",
    "searchText": "3.3 security & xss sanitization statutory gstr-1 tax invoice specification & deterministic integer tax engine to prevent cross-site scripting (xss) or html tag breakout from untrusted merchant or product metadata, all dynamic strings (sku identifiers, product titles, invoice numbers, merchant legal names, gstins, and timestamps) are sanitized using html.escape(value, quote=true) prior to string template interpolation. ---"
  },
  {
    "route": "/docs/gstr1-invoice#4-cryptographic-audit-digest--non-repudiation",
    "docTitle": "Statutory GSTR-1 Tax Invoice Specification & Deterministic Integer Tax Engine",
    "headingText": "4. Cryptographic Audit Digest & Non-Repudiation",
    "snippet": "For complete e-invoicing audit compliance and tamper-evidence, every generated tax invoice computes a Canonical JSON SHA-256 Digest following RFC 8785 (JSON...",
    "searchText": "4. cryptographic audit digest & non-repudiation statutory gstr-1 tax invoice specification & deterministic integer tax engine for complete e-invoicing audit compliance and tamper-evidence, every generated tax invoice computes a canonical json sha-256 digest following rfc 8785 (json canonicalization scheme - jcs) ."
  },
  {
    "route": "/docs/gstr1-invoice#41-canonical-jcs-payload-construction",
    "docTitle": "Statutory GSTR-1 Tax Invoice Specification & Deterministic Integer Tax Engine",
    "headingText": "4.1 Canonical JCS Payload Construction",
    "snippet": "The invoice dictionary is normalized with deterministic key ordering and zero unquoted whitespace:",
    "searchText": "4.1 canonical jcs payload construction statutory gstr-1 tax invoice specification & deterministic integer tax engine the invoice dictionary is normalized with deterministic key ordering and zero unquoted whitespace:"
  },
  {
    "route": "/docs/gstr1-invoice#42-cryptographic-hash-computation",
    "docTitle": "Statutory GSTR-1 Tax Invoice Specification & Deterministic Integer Tax Engine",
    "headingText": "4.2 Cryptographic Hash Computation",
    "snippet": "The canonicalized UTF-8 bytes are passed through SHA-256: This yields a 64-character hexadecimal digest (e.g.,...",
    "searchText": "4.2 cryptographic hash computation statutory gstr-1 tax invoice specification & deterministic integer tax engine the canonicalized utf-8 bytes are passed through sha-256: this yields a 64-character hexadecimal digest (e.g., a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90 ), which is stamped into the invoice document and recorded on the ledger for statutory tax reconciliation. ---"
  },
  {
    "route": "/docs/gstr1-invoice#5-indian-gst-2-digit-state-code-registry",
    "docTitle": "Statutory GSTR-1 Tax Invoice Specification & Deterministic Integer Tax Engine",
    "headingText": "5. Indian GST 2-Digit State Code Registry",
    "snippet": "The tax engine includes an internal registry mapping all 37 official two-digit Indian GST state and Union Territory codes: Code State / Union Territory Code...",
    "searchText": "5. indian gst 2-digit state code registry statutory gstr-1 tax invoice specification & deterministic integer tax engine the tax engine includes an internal registry mapping all 37 official two-digit indian gst state and union territory codes: code state / union territory code state / union territory --- --- --- --- 01 jammu & kashmir 20 jharkhand 02 himachal pradesh 21 odisha 03 punjab 22 chhattisgarh 04 chandigarh 23 madhya pradesh 05 uttarakhand 24 gujarat 06 haryana 26 dadra & nagar haveli and daman & diu 07 delhi 27 maharashtra 08 rajasthan 29 karnataka 09 uttar pradesh 30 goa 10 bihar 31 lakshadweep 11 sikkim 32 kerala 12 arunachal pradesh 33 tamil nadu 13 nagaland 34 puducherry 14 manipur 35 andaman & nicobar islands 15 mizoram 36 telangana 16 tripura 37 andhra pradesh 17 meghalaya 38 ladakh 18 assam 97 other territory 19 west bengal ---"
  },
  {
    "route": "/docs/gstr1-invoice#6-verification--automated-unit-testing",
    "docTitle": "Statutory GSTR-1 Tax Invoice Specification & Deterministic Integer Tax Engine",
    "headingText": "6. Verification & Automated Unit Testing",
    "snippet": "Verify the GSTR-1 tax calculation engine and HTML rendering pipeline using pytest:",
    "searchText": "6. verification & automated unit testing statutory gstr-1 tax invoice specification & deterministic integer tax engine verify the gstr-1 tax calculation engine and html rendering pipeline using pytest:"
  }
];
