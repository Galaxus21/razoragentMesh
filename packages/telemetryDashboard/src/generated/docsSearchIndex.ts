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
    "docTitle": "Setup and installation",
    "headingText": "",
    "snippet": "Everything needed to get the mesh running on your own machine: what to install, what to put in .env , one command to start seven services, and how to tell when...",
    "searchText": " setup and installation everything needed to get the mesh running on your own machine: what to install, what to put in .env , one command to start seven services, and how to tell when they are ready. allow about ten minutes, most of it docker pulling images. ---"
  },
  {
    "route": "/docs/setup#prerequisites",
    "docTitle": "Setup and installation",
    "headingText": "Prerequisites",
    "snippet": "Before launching RazorAgent Mesh, verify your local system meets the following version requirements: - Node.js : v20.10.0+ (LTS) or v22.0.0+ with npm - Python...",
    "searchText": "prerequisites setup and installation before launching razoragent mesh, verify your local system meets the following version requirements: - node.js : v20.10.0+ (lts) or v22.0.0+ with npm - python : v3.11.0+ (compatible with 3.12 and 3.13 ) with pip - docker & docker compose : docker v24+ (compose v2.20+ ) - redis : v7.0+ (in-memory state, pub/sub, and distributed locks) - qdrant : v1.7.0+ (vector search engine on port 6333) ---"
  },
  {
    "route": "/docs/setup#packages-and-ports",
    "docTitle": "Setup and installation",
    "headingText": "Packages and ports",
    "snippet": "When running the mesh locally (via Docker Compose or native processes), each microservice listens on a dedicated localhost port: Localhost Port Microservice...",
    "searchText": "packages and ports setup and installation when running the mesh locally (via docker compose or native processes), each microservice listens on a dedicated localhost port: localhost port microservice protocol / layer responsibility & role key endpoints --- --- --- --- --- localhost:8000 mandate engine rest / sse (layer 4 & 5) ap2 cryptographic mandate verification (ed25519), 2-phase commit (2pc) multi-party settlement sagas, statutory gstr-1 tax invoicing, and live server-sent events (sse) telemetry stream. get /health post /api/v1/settlement/execute get /api/v1/telemetry/stream localhost:4002 merchant api rest (layer 1) merchant did registration, autonomous negotiation policy configuration, multi-channel catalog ingestion (rest, csv, shopify, erp), domain facets, and dynamic mcx bullion pricing. get /health post /api/v1/merchant/register post /api/v1/merchant/{merchantdid}/catalog localhost:4003 x402 gateway rest (layer 0 & 2) dynamic http 402 negotiation gateway, sha-256 proof-of-work (pow) sybil/anti-spam shield, rubinstein-ståhl bilateral bargaining engine, and ast contract compilation. get /api/v1/mesh/health post /api/v1/mesh/negotiate get /api/v1/mesh/challenge localhost:4001 mcp server json-rpc 2.0 (layer 1) model context protocol server exposing ten tools to autonomous ai buyer agents: discovery ( search catalog , browse catalog ), commerce ( get live sku quote , negotiate price , reserve inventory lock , verify shipping sla ) and purchase ( establish agent delegation , create cart mandate , sign execution mandate , execute settlement ). post /mcp (streamable http) post /rpc stdio pipe localhost:3000 telemetry dashboard web / http (layer 5) real-time next.js 15 web inspector, visual audit trail, dynamic markdown documentation viewer, and universal sku studio. get / get /overview get /docs/setup localhost:6333 qdrant vector db rest / grpc (layer 3) high-speed vector search engine providing approximate nearest neighbor (ann) cosine similarity search and sub-300ms out-of-stock vector cart healing. get /healthz post /collections/merchant catalog/points/search localhost:6379 redis state store tcp (layer 0–4) distributed in-memory cache, atomic lua inventory locking with monotonic fencing tokens, pub/sub event bus, and single-use anti-replay nonce ledger. ping (via redis-cli) ---"
  },
  {
    "route": "/docs/setup#environment-configuration",
    "docTitle": "Setup and installation",
    "headingText": "Environment configuration",
    "snippet": "Create your .env file in razoragentMesh/ . It is shorter than you might expect: docker-compose.yml sets each service's port and Redis URL directly, so the only...",
    "searchText": "environment configuration setup and installation create your .env file in razoragentmesh/ . it is shorter than you might expect: docker-compose.yml sets each service's port and redis url directly, so the only values it interpolates from .env are the two signing keys and the dashboard's stream url. running a service outside docker means supplying what compose would otherwise set: every variable above is read by code. earlier revisions of this guide also listed telemetry port , merchant api port , gateway port , mcp server port , qdrant collection name , razorpay webhook secret , ed25519 private key and ap2 gate daily limit paise . nothing reads any of them — setting them has no effect, and ed25519 private key in particular looked like the way to supply a signing key while the code was reading merchant private key hex . they have been removed rather than left to mislead. that list previously also named qdrant host , qdrant port , razorpay key id and razorpay key secret . all four are read by code and are documented above instead: the qdrant pair by the merchant api's auto-vectorizer, the razorpay credentials by the mandate engine, where they enable the live orders api and decouple it from route split transfers. ---"
  },
  {
    "route": "/docs/setup#start-the-stack",
    "docTitle": "Setup and installation",
    "headingText": "Start the stack",
    "snippet": "Start the full 7-service mesh in the background:",
    "searchText": "start the stack setup and installation start the full 7-service mesh in the background:"
  },
  {
    "route": "/docs/setup#verify-each-service",
    "docTitle": "Setup and installation",
    "headingText": "Verify each service",
    "snippet": "docker compose ps should show seven services healthy. To check them individually: Every line should print 200 . The four mesh services, with the package that...",
    "searchText": "verify each service setup and installation docker compose ps should show seven services healthy. to check them individually: every line should print 200 . the four mesh services, with the package that implements each: settlement coordinator, mandate verification and the gstr-1 tax engine. merchant registration, gstin validation and catalog ingestion. proof-of-work ingress and the bilateral negotiation state machine. the mcp tool surface an agent connects to. qdrant answers on http://localhost:6333/healthz and redis on docker compose exec redis redis-cli ping ; neither is a mesh service, so neither appears in the registry above. once everything is healthy, open the dashboard at http://localhost:3000 and follow the agent quickstart to put an agent through the stack. ---"
  },
  {
    "route": "/docs/setup#running-without-docker",
    "docTitle": "Setup and installation",
    "headingText": "Running without Docker",
    "snippet": "To run individual packages on your host machine without Docker:",
    "searchText": "running without docker setup and installation to run individual packages on your host machine without docker:"
  },
  {
    "route": "/docs/agent-quickstart",
    "docTitle": "Agent quickstart",
    "headingText": "",
    "snippet": "Run the mesh, point your own AI agent at it, and watch a cryptographically signed purchase complete while the dashboard renders each step live. The intended...",
    "searchText": " agent quickstart run the mesh, point your own ai agent at it, and watch a cryptographically signed purchase complete while the dashboard renders each step live. the intended setup is two windows side by side: the dashboard on one , your agent on the other . you publish a product in the dashboard, ask your agent to buy it in plain language, and watch the protocol execute in real time. ---"
  },
  {
    "route": "/docs/agent-quickstart#1-start-the-mesh",
    "docTitle": "Agent quickstart",
    "headingText": "1. Start the mesh",
    "snippet": "Seven services. Wait for all of them to report healthy: razoragent catalog seeder showing Exited (0) is correct — it is a one-shot job that loads the fixture...",
    "searchText": "1. start the mesh agent quickstart seven services. wait for all of them to report healthy: razoragent catalog seeder showing exited (0) is correct — it is a one-shot job that loads the fixture catalog and stops. open the dashboard at http://localhost:3000/overview . leave it open; it is one half of the demo. ---"
  },
  {
    "route": "/docs/agent-quickstart#2-connect-your-agent",
    "docTitle": "Agent quickstart",
    "headingText": "2. Connect your agent",
    "snippet": "The MCP server speaks two transports. Use whichever your client supports.",
    "searchText": "2. connect your agent agent quickstart the mcp server speaks two transports. use whichever your client supports."
  },
  {
    "route": "/docs/agent-quickstart#streamable-http-recommended",
    "docTitle": "Agent quickstart",
    "headingText": "Streamable HTTP (recommended)",
    "snippet": "The mesh is already serving it. Point your client at: For Claude Code:",
    "searchText": "streamable http (recommended) agent quickstart the mesh is already serving it. point your client at: for claude code:"
  },
  {
    "route": "/docs/agent-quickstart#stdio",
    "docTitle": "Agent quickstart",
    "headingText": "stdio",
    "snippet": "For clients that spawn a process instead. Build once: Then register this command: MCP TRANSPORT=stdio is required, not optional. Without it the process also...",
    "searchText": "stdio agent quickstart for clients that spawn a process instead. build once: then register this command: mcp transport=stdio is required, not optional. without it the process also tries to bind port 4001, which docker already holds, and the session dies before the first tool call. use absolute paths for cwd if your client does not resolve relative ones."
  },
  {
    "route": "/docs/agent-quickstart#confirm-the-connection",
    "docTitle": "Agent quickstart",
    "headingText": "Confirm the connection",
    "snippet": "Ask your agent to list its tools. You should see ten : They are listed in the order they are meant to be called: Tool What it does --- --- establish agent...",
    "searchText": "confirm the connection agent quickstart ask your agent to list its tools. you should see ten : they are listed in the order they are meant to be called: tool what it does --- --- establish agent delegation pairs your agent, issues a signed intent mandate search catalog natural-language product discovery browse catalog lists what the mesh sells, with filters and paging get live sku quote live price, tax and discount for a sku negotiate price bargains for a lower unit price over x402-inr reserve inventory lock atomic stock reservation with a fencing token verify shipping sla serviceability and delivery-tier check create cart mandate merchant-signed cart at mesh-derived prices sign execution mandate binds intent and cart into an execution mandate execute settlement runs the 2pc settlement saga two of these are optional. browse catalog is there for when you cannot phrase a good search query, or want to see the range before choosing. negotiate price runs a real alternating-offer negotiation -- five turns, each gated by a proof-of-work solve and charged ₹0.50 from a micro-escrow it opens and releases for you. it is worth a call on anything expensive and a waste on anything cheap, and it reports both the saving and the fees so your agent can tell which. negotiating does not itself produce a price you can buy at. call get live sku quote again once the session converges: the agreed price comes back on the fresh quote as a negotiated discount line, and that quote's quote hash is what the cart binds to. pair first. in mesh demo custodial the mesh mints your buyer did inside establish agent delegation , so a buyer agent id to quote with does not exist until you have called it. ---"
  },
  {
    "route": "/docs/agent-quickstart#3-publish-something-to-buy",
    "docTitle": "Agent quickstart",
    "headingText": "3. Publish something to buy",
    "snippet": "In the dashboard, open Merchant Studio and publish a product — give it a title your agent can find in plain language, like Ergonomic Mesh Office Chair with...",
    "searchText": "3. publish something to buy agent quickstart in the dashboard, open merchant studio and publish a product — give it a title your agent can find in plain language, like ergonomic mesh office chair with lumbar support . publishing writes the listing to redis and indexes it in qdrant, so it becomes discoverable to search catalog immediately. the mesh boots with two seeded sets -- industrial parts and office equipment -- so give yours a distinctive title if you want it easy to pick out of search results. anything you publish lives in the running containers, not in the fixtures — docker compose down -v removes it. ---"
  },
  {
    "route": "/docs/agent-quickstart#4-ask-your-agent-to-buy-it",
    "docTitle": "Agent quickstart",
    "headingText": "4. Ask your agent to buy it",
    "snippet": "Prompt in plain language. The tool descriptions carry the ordering rules, so a capable agent sequences the calls itself: Find me something comfortable to sit...",
    "searchText": "4. ask your agent to buy it agent quickstart prompt in plain language. the tool descriptions carry the ordering rules, so a capable agent sequences the calls itself: find me something comfortable to sit on while working at a desk. establish a delegation with a ₹9,000 budget using mesh demo custodial custody, then buy two of the best match, delivering to pincode 560001, state code 29. the agent will work through: pair → discover → quote → lock → cart → sign → settle. pair first. in custodial mode the mesh mints the buyer did, and every later call must use that did — get live sku quote and reserve inventory lock both take it as buyer agent id . the settlement gate rejects a chain whose execution mandate was signed by a different agent than the intent mandate delegated to. one parameter is easy to miss: reserve inventory lock returns its signature under the key signature , but create cart mandate expects it as lock signature . pass the value through unchanged. quote before you lock. reserve inventory lock only reserves stock against a quote hash this mesh issued for that exact sku, quantity and buyer agent id . a hash it does not recognise is refused and no stock is reserved , so the refusal costs nothing and names what to fix — quote first, quote again because yours lapsed, or quote for what you actually meant to lock. mind the two clocks while you are here: a lock lasts lock ttl seconds , but the quote behind it dies 60 seconds after it was issued, and create cart mandate needs both alive. taking a 120-second lock does not buy a 120-second quote."
  },
  {
    "route": "/docs/agent-quickstart#reading-the-settlement-response",
    "docTitle": "Agent quickstart",
    "headingText": "Reading the settlement response",
    "snippet": "A successful settlement returns a capture, the split across recipients, a statutory GSTR-1 invoice, and -- when Razorpay test credentials are configured -- a...",
    "searchText": "reading the settlement response agent quickstart a successful settlement returns a capture, the split across recipients, a statutory gstr-1 invoice, and -- when razorpay test credentials are configured -- a real razorpay order id: the four transfers sum to the grand total, and the tax is recomputed independently by the settlement enclave rather than trusted from the cart. two of those fields come from different places, and the difference matters: - razorpayorderid is a real order at razorpay , created through the orders api and carrying this run's cartmandatehash and executionid in its notes . fetch it back with your test keys and the audit trail continues outside the mesh. it appears only when razorpay key id and razorpay key secret are set; see environment configuration. - paymentid and transfers come from the mock ledger . the split is computed for real and conserves the total to the paise, but it is not executed at razorpay: route transfers need account activation and real linked accounts, so they stay on the mock until razorpay route live=true . the order is payable by a person -- that is what the dashboard's settle screen is for -- and paying it is what produces a genuine razorpay pay ... id. note that tool inputs are snake case while settlement output is camelcase ; the settlement response is the mandate engine's own schema, passed through unmodified."
  },
  {
    "route": "/docs/agent-quickstart#when-the-mesh-refuses",
    "docTitle": "Agent quickstart",
    "headingText": "When the mesh refuses",
    "snippet": "A refusal — replayed nonce, expired inventory lock, budget exceeded, unauthorized category, bad signature — comes back as a tool result with isError set , not...",
    "searchText": "when the mesh refuses agent quickstart a refusal — replayed nonce, expired inventory lock, budget exceeded, unauthorized category, bad signature — comes back as a tool result with iserror set , not as a json-rpc error, carrying a machine-readable reason. that distinction matters: a refusal means the protocol worked. an agent that only inspects the json-rpc error field will read a correct refusal as a success. ---"
  },
  {
    "route": "/docs/agent-quickstart#5-watch-it-live",
    "docTitle": "Agent quickstart",
    "headingText": "5. Watch it live",
    "snippet": "Open Protocol Playground - Live Agent ( /playground/live-agent ) in the dashboard window. It groups incoming telemetry by MCP session, so your agent's run...",
    "searchText": "5. watch it live agent quickstart open protocol playground - live agent ( /playground/live-agent ) in the dashboard window. it groups incoming telemetry by mcp session, so your agent's run appears as one pipeline: each stage lands as the call is made, with the package that did the work, the arguments sent and the result returned. two agents connected at once stay in separate sessions. the distinction the page is careful about: a refused stage is the protocol working -- a replayed nonce or an over-budget cart being rejected -- and is rendered in accent, never in error red. failed is reserved for something genuinely breaking, such as a service falling over. every tool call publishes mcp tool call and mcp tool result to the telemetry stream, tagged with the mcp session id, so one agent's run groups into one visible sequence. to watch the raw stream: ---"
  },
  {
    "route": "/docs/agent-quickstart#6-key-custody",
    "docTitle": "Agent quickstart",
    "headingText": "6. Key custody",
    "snippet": "Signing the Execution Mandate requires the buyer's private key . Whoever holds that key can spend the buyer's money without the buyer. key custody has no...",
    "searchText": "6. key custody agent quickstart signing the execution mandate requires the buyer's private key . whoever holds that key can spend the buyer's money without the buyer. key custody has no default; you must state it."
  },
  {
    "route": "/docs/agent-quickstart#agent_held--non-custodial",
    "docTitle": "Agent quickstart",
    "headingText": "agent_held — non-custodial",
    "snippet": "Your agent generates its own Ed25519 keypair and never gives it to the mesh. It proves possession by signing the budget terms at pairing. sign execution...",
    "searchText": "agent_held — non-custodial agent quickstart your agent generates its own ed25519 keypair and never gives it to the mesh. it proves possession by signing the budget terms at pairing. sign execution mandate then returns the exact rfc 8785 canonical json and its sha-256 digest, and no signature — your agent signs those bytes itself and passes 128 lowercase hex to execute settlement . the mesh holds no buyer authority at any point. this is the mode where the mandate chain proves what it appears to prove. settle promptly: the nonce ledger rejects an execution mandate signed outside a 65 second window."
  },
  {
    "route": "/docs/agent-quickstart#mesh_demo_custodial--custodial-demo-only",
    "docTitle": "Agent quickstart",
    "headingText": "mesh_demo_custodial — custodial, demo only",
    "snippet": "The mesh mints and holds the buyer key, and returns the private key to you in the pairing response — a custodial demo that hands you the key cannot be mistaken...",
    "searchText": "mesh_demo_custodial — custodial, demo only agent quickstart the mesh mints and holds the buyer key, and returns the private key to you in the pairing response — a custodial demo that hands you the key cannot be mistaken for a security boundary. be precise about the cost. in this mode the mesh can sign execution mandates with no human approval. and because the demo mesh also holds the principal key that signs the intent mandate, it can mint itself a fresh delegation with any budget it likes. every signature still verifies; the budget ceiling constrains your agent, not the mesh. the chain proves internal consistency, not that a human authorized the spend. use it when the driving agent cannot perform detached ed25519 signing. use agent held for any claim about what the protocol guarantees."
  },
  {
    "route": "/docs/agent-quickstart#the-production-path",
    "docTitle": "Agent quickstart",
    "headingText": "The production path",
    "snippet": "Split custody: the human's principal key never enters the mesh, the Intent Mandate is signed out-of-band, and the mesh may then hold only an ephemeral session...",
    "searchText": "the production path agent quickstart split custody: the human's principal key never enters the mesh, the intent mandate is signed out-of-band, and the mesh may then hold only an ephemeral session key bounded by a delegation it cannot forge. that is what upi circle actually models. ---"
  },
  {
    "route": "/docs/agent-quickstart#7-what-is-enforced-and-what-is-not",
    "docTitle": "Agent quickstart",
    "headingText": "7. What is enforced, and what is not",
    "snippet": "Enforced at settlement, with ₹0 charged on failure: - Budget caps — max budget and single-transaction limit - Delegated agent binding — the execution mandate's...",
    "searchText": "7. what is enforced, and what is not agent quickstart enforced at settlement, with ₹0 charged on failure: - budget caps — max budget and single-transaction limit - delegated agent binding — the execution mandate's signer must be the did the intent delegated to - category authorization — cart lines outside authorized categories abort the settlement - arithmetic enclave — line totals, tax and the settlement amount are recomputed, not trusted - inventory lock expiry — a lapsed reservation refuses to settle - nonce replay and cart replay — single-use, enforced by the ledger - mandate expiry and full ed25519 signature-chain verification known limits, stated plainly: - no money moves. without real razorpay credentials the route client is a mock. the split and the invoice are computed for real; the transfer is simulated. - merchant private key hex falls back to a literal committed in the repo. any deployment that does not set it signs cart mandates with a key anyone can read. docker-compose.yml passes an empty value by default, which takes that fallback. - servertime is a client-controlled clock override on the mandate engine's http surface. these mcp tools deliberately do not expose it, but anything calling the engine directly can. - the cumulative-budget ledger fails open if redis is unavailable, leaving per-transaction checks as the only budget defence. - agent identity is ephemeral. keys are never persisted and do not survive a restart. ---"
  },
  {
    "route": "/docs/agent-quickstart#troubleshooting",
    "docTitle": "Agent quickstart",
    "headingText": "Troubleshooting",
    "snippet": "Symptom-by-symptom fixes — port conflicts, handshake failures, degraded search, dark dashboard panels — are in docs/AGENT SETUP TROUBLESHOOTING.md.",
    "searchText": "troubleshooting agent quickstart symptom-by-symptom fixes — port conflicts, handshake failures, degraded search, dark dashboard panels — are in docs/agent setup troubleshooting.md."
  },
  {
    "route": "/docs/onboarding",
    "docTitle": "Developer onboarding",
    "headingText": "",
    "snippet": "This guide is the path from a running stack to a settled purchase. It covers the protocol's shape, the identities and keys every actor needs, what a merchant...",
    "searchText": " developer onboarding this guide is the path from a running stack to a settled purchase. it covers the protocol's shape, the identities and keys every actor needs, what a merchant publishes, what a buyer agent calls, and how a settlement is verified -- in the order you meet them. it is deliberately the narrative route. where a topic has its own reference, this page gives you enough to keep moving and links there rather than restating it: if you want read --- --- to get the stack running setup & installation to point an existing agent at the mesh agent quickstart every argument of every mcp tool tool reference to publish and price a catalog merchant guide to build a buyer with the sdk buyer sdk the event stream and its schemas telemetry how tax and invoices are computed gstr-1 invoicing"
  },
  {
    "route": "/docs/onboarding#how-the-mesh-fits-together",
    "docTitle": "Developer onboarding",
    "headingText": "How the mesh fits together",
    "snippet": "RazorAgent Mesh v2.0 is an open, decentralized agentic commerce protocol designed for autonomous machine-to-machine transactions over Indian sovereign payment...",
    "searchText": "how the mesh fits together developer onboarding razoragent mesh v2.0 is an open, decentralized agentic commerce protocol designed for autonomous machine-to-machine transactions over indian sovereign payment rails (upi circle, razorpay route) and tax frameworks (gst rule 46 / gstr-1)."
  },
  {
    "route": "/docs/onboarding#the-six-layers",
    "docTitle": "Developer onboarding",
    "headingText": "The six layers",
    "snippet": "The protocol operates across 6 distinct cryptographic, discovery, negotiation, settlement and observability layers, numbered L0 to L5 exactly as the canonical...",
    "searchText": "the six layers developer onboarding the protocol operates across 6 distinct cryptographic, discovery, negotiation, settlement and observability layers, numbered l0 to l5 exactly as the canonical map in packages/telemetrydashboard/src/constants/protocollayermap.ts defines them:"
  },
  {
    "route": "/docs/onboarding#guarantees-the-mesh-enforces",
    "docTitle": "Developer onboarding",
    "headingText": "Guarantees the mesh enforces",
    "snippet": "Seven properties hold for every transaction. They are enforced in code, not asserted in prose, and each row names the module that enforces it. Guarantee What...",
    "searchText": "guarantees the mesh enforces developer onboarding seven properties hold for every transaction. they are enforced in code, not asserted in prose, and each row names the module that enforces it. guarantee what it means enforced in --- --- --- integer paise arithmetic every monetary value is a positive integer number of paise. a float anywhere on a money path raises arithmeticdriftexception rather than rounding. arithmeticenclave.py , jcscanonicalizer.ts equal-half gst division cgst and sgst are separate levies at half the combined rate each, so both come from the same expression and are equal by construction. deriving one as the remainder of the other yields an illegal split on odd slabs such as 5%. see gstr-1 invoicing. arithmeticenclave.py , pricingengine.ts ed25519 canonical signatures detached 64-byte signatures over rfc 8785 (jcs) canonical bytes, so the same document serialises identically on both runtimes. agentkeymanager , ed25519verifier ap2 budget gate a settlement may not exceed the delegated budget or the per-transaction ceiling, whichever is lower, and its category must be one the user authorised. budgetgate.py , agentmandatebuilder.ts anti-replay nonces each nonce is single-use, recorded with a redis setnx and a 120s ttl, and accepted only within 5s behind to 60s ahead of server time. nonceledger.py negotiation monotonicity buyer bids never decrease and seller asks never increase, and the seller's floor is the merchant's policy, never the buyer's request. bidstatemachine.py atomic inventory fencing stock decrement and fencing-token increment happen in one redis lua script, so two agents cannot be sold the same unit. inventorylocker.ts , redislockmanager.ts ---"
  },
  {
    "route": "/docs/onboarding#repository-layout",
    "docTitle": "Developer onboarding",
    "headingText": "Repository layout",
    "snippet": "Eight packages, each owning one layer's worth of the protocol. The ports are the ones docker-compose.yml binds. Prerequisites, the .env template and the...",
    "searchText": "repository layout developer onboarding eight packages, each owning one layer's worth of the protocol. the ports are the ones docker-compose.yml binds. prerequisites, the .env template and the command that starts all of this live in setup & installation. come back here once docker compose ps shows seven healthy services. ---"
  },
  {
    "route": "/docs/onboarding#keys-and-identities",
    "docTitle": "Developer onboarding",
    "headingText": "Keys and identities",
    "snippet": "All actors in the mesh (Merchants, Buyer Agents, CFO/Users) are identified by Decentralized Identifiers (DIDs) rooted in Ed25519 public verification keys.",
    "searchText": "keys and identities developer onboarding all actors in the mesh (merchants, buyer agents, cfo/users) are identified by decentralized identifiers (dids) rooted in ed25519 public verification keys."
  },
  {
    "route": "/docs/onboarding#did-formats",
    "docTitle": "Developer onboarding",
    "headingText": "DID formats",
    "snippet": "Actor Type DID Format Public Key Component Example --- --- --- --- Merchant did:razoragent:merchant: First 16 hex characters of Ed25519 Verify Key...",
    "searchText": "did formats developer onboarding actor type did format public key component example --- --- --- --- merchant did:razoragent:merchant: first 16 hex characters of ed25519 verify key did:razoragent:merchant:9f8e7d6c5b4a3210 buyer agent did:razoragent:buyer: first 16 hex characters of ed25519 verify key did:razoragent:buyer:ad1b82a9cce6d365 user / cfo did:razoragent:user: first 16 hex characters of ed25519 verify key did:razoragent:user:ec89f8790fa0bc33"
  },
  {
    "route": "/docs/onboarding#generating-a-keypair-in-python",
    "docTitle": "Developer onboarding",
    "headingText": "Generating a keypair in Python",
    "snippet": "",
    "searchText": "generating a keypair in python developer onboarding "
  },
  {
    "route": "/docs/onboarding#generating-a-keypair-in-typescript",
    "docTitle": "Developer onboarding",
    "headingText": "Generating a keypair in TypeScript",
    "snippet": "---",
    "searchText": "generating a keypair in typescript developer onboarding ---"
  },
  {
    "route": "/docs/onboarding#onboarding-a-merchant",
    "docTitle": "Developer onboarding",
    "headingText": "Onboarding a merchant",
    "snippet": "The Merchant Onboarding flow registers regulatory credentials, provisions autonomous negotiation parameters, ingests multi-vertical product catalogs,...",
    "searchText": "onboarding a merchant developer onboarding the merchant onboarding flow registers regulatory credentials, provisions autonomous negotiation parameters, ingests multi-vertical product catalogs, configures dynamic bullion pricing rules, and publishes skus to the mesh."
  },
  {
    "route": "/docs/onboarding#step-1-register-the-merchant",
    "docTitle": "Developer onboarding",
    "headingText": "Step 1: Register the merchant",
    "snippet": "Merchants submit statutory GSTIN details, their registered Razorpay Route linked account ( acc ... ), contact email, and dispatch origin pincode to the...",
    "searchText": "step 1: register the merchant developer onboarding merchants submit statutory gstin details, their registered razorpay route linked account ( acc ... ), contact email, and dispatch origin pincode to the merchantapi service on port 4002 . validation rules 1. gstin checksum : verified via indian gst luhn mod-36 algorithm ( ^[0-9]{2}[a-z]{5}[0-9]{4}[a-z]{1}[1-9a-z]{1}z[0-9a-z]{1}$ ). 2. razorpay route account : must match prefix acc with minimum length 14. 3. origin pincode : 6 digits starting with 1-9 ( ^[1-9][0-9]{5}$ ). registration request registration response ---"
  },
  {
    "route": "/docs/onboarding#step-2-set-the-negotiation-policy",
    "docTitle": "Developer onboarding",
    "headingText": "Step 2: Set the negotiation policy",
    "snippet": "Merchants define their automated concession limits for bilateral bargaining with AI buyer agents. The negotiation state machine enforces these boundaries...",
    "searchText": "step 2: set the negotiation policy developer onboarding merchants define their automated concession limits for bilateral bargaining with ai buyer agents. the negotiation state machine enforces these boundaries server-side. policy parameters - negotiationenabled : the opt-in. defaults to false , so a policy that omits it is a policy that refuses to bargain -- every other parameter here only describes how you negotiate. - marginfloorbps : maximum discount floor in basis points (e.g., 800 = 8.00% max discount). - minimumorderquantity : minimum order quantity eligible for dynamic bargaining. - autoacceptspreadpaise : spread in paise below which a counter-offer is automatically accepted. - maxnegotiationturns : ceiling on bargaining turns. the policy accepts 1 to 10, but the gateway clamps every session to maxnegotiationturns = 5 , so a higher number has no effect until that constant moves. policy request ---"
  },
  {
    "route": "/docs/onboarding#step-3-ingest-the-catalog",
    "docTitle": "Developer onboarding",
    "headingText": "Step 3: Ingest the catalog",
    "snippet": "RazorAgent Mesh provides four distinct programmatic ingestion adapters: A single SKU over REST Endpoint: POST /api/v1/merchant/{merchantDid}/catalog Bulk CSV...",
    "searchText": "step 3: ingest the catalog developer onboarding razoragent mesh provides four distinct programmatic ingestion adapters: a single sku over rest endpoint: post /api/v1/merchant/{merchantdid}/catalog bulk csv upload, up to 500 rows a batch endpoint: post /api/v1/merchant/{merchantdid}/bulk-csv create catalog batch.csv : upload csv via curl: shopify webhook endpoint: post /api/v1/merchant/{merchantdid}/shopify-sync receives standard shopify products/create and products/update webhooks. variants are automatically mapped to sku format shopify-{productid}-{variantid} and shopify tags are parsed into domain facets ( promo:... , allergens:... , salt:... , 18k / 22k / 24k ). erp stock and price sync endpoint: post /api/v1/merchant/{merchantdid}/erp-sync ---"
  },
  {
    "route": "/docs/onboarding#step-4-add-domain-facets",
    "docTitle": "Developer onboarding",
    "headingText": "Step 4: Add domain facets",
    "snippet": "RazorAgent Mesh supports 4 multi-industry domain facets: ---",
    "searchText": "step 4: add domain facets developer onboarding razoragent mesh supports 4 multi-industry domain facets: ---"
  },
  {
    "route": "/docs/onboarding#step-5-price-bullion-from-the-spot-oracle",
    "docTitle": "Developer onboarding",
    "headingText": "Step 5: Price bullion from the spot oracle",
    "snippet": "For precious metals (Gold 24K, Gold 22K, Silver), merchants can attach a DynamicPricingRule to evaluate real-time quotations linked directly to MCX spot feeds....",
    "searchText": "step 5: price bullion from the spot oracle developer onboarding for precious metals (gold 24k, gold 22k, silver), merchants can attach a dynamicpricingrule to evaluate real-time quotations linked directly to mcx spot feeds. the pricing formula a bullion sku payload ---"
  },
  {
    "route": "/docs/onboarding#step-6-resolve-the-hsn-code-and-gst-rate",
    "docTitle": "Developer onboarding",
    "headingText": "Step 6: Resolve the HSN code and GST rate",
    "snippet": "RazorAgent Mesh enforces statutory GST rates based on Indian HSN/SAC classifications: Category HSN Code Statutory GST Rate Tax Split (Intra-State) Tax Split...",
    "searchText": "step 6: resolve the hsn code and gst rate developer onboarding razoragent mesh enforces statutory gst rates based on indian hsn/sac classifications: category hsn code statutory gst rate tax split (intra-state) tax split (inter-state) --- --- --- --- --- precious jewelry 7113 3% 1.5% cgst + 1.5% sgst 3.0% igst apparel (< ₹1,000) 6109 5% 2.5% cgst + 2.5% sgst 5.0% igst apparel ( ₹1,000) 6203 12% 6.0% cgst + 6.0% sgst 12.0% igst pharmaceuticals 3004 5% / 12% 2.5% cgst + 2.5% sgst 5.0% / 12.0% igst packaged foods (fmcg) 2106 12% / 18% 6.0% cgst + 6.0% sgst 12.0% / 18.0% igst electronics & hardware 8471 18% 9.0% cgst + 9.0% sgst 18.0% igst luxury / automobiles 8703 28% 14.0% cgst + 14.0% sgst 28.0% igst ---"
  },
  {
    "route": "/docs/onboarding#step-7-publish-a-sku",
    "docTitle": "Developer onboarding",
    "headingText": "Step 7: Publish a SKU",
    "snippet": "Merchants can use a lightweight Python or Node.js publishing script to automate catalog registration and live updates: ---",
    "searchText": "step 7: publish a sku developer onboarding merchants can use a lightweight python or node.js publishing script to automate catalog registration and live updates: ---"
  },
  {
    "route": "/docs/onboarding#onboarding-a-buyer-agent",
    "docTitle": "Developer onboarding",
    "headingText": "Onboarding a buyer agent",
    "snippet": "AI Buyer Agents execute automated purchasing workflows within principal-delegated spending constraints.",
    "searchText": "onboarding a buyer agent developer onboarding ai buyer agents execute automated purchasing workflows within principal-delegated spending constraints."
  },
  {
    "route": "/docs/onboarding#step-1-install-the-sdk",
    "docTitle": "Developer onboarding",
    "headingText": "Step 1: Install the SDK",
    "snippet": "TypeScript Python ---",
    "searchText": "step 1: install the sdk developer onboarding typescript python ---"
  },
  {
    "route": "/docs/onboarding#step-2-hold-a-key-and-declare-a-budget",
    "docTitle": "Developer onboarding",
    "headingText": "Step 2: Hold a key and declare a budget",
    "snippet": "Initialize the AgentKeyManager and configure the human principal's spending delegation limits: ---",
    "searchText": "step 2: hold a key and declare a budget developer onboarding initialize the agentkeymanager and configure the human principal's spending delegation limits: ---"
  },
  {
    "route": "/docs/onboarding#step-3-create-the-intent-mandate",
    "docTitle": "Developer onboarding",
    "headingText": "Step 3: Create the Intent Mandate",
    "snippet": "The user signs an immutable Intent Mandate ( ) establishing strict financial and category limits: ---",
    "searchText": "step 3: create the intent mandate developer onboarding the user signs an immutable intent mandate ( ) establishing strict financial and category limits: ---"
  },
  {
    "route": "/docs/onboarding#step-4-discover-a-product-and-read-its-price",
    "docTitle": "Developer onboarding",
    "headingText": "Step 4: Discover a product and read its price",
    "snippet": "The buyer agent queries the Layer 1 MCP tool get live sku quote and receives a dynamic quote with automated discount stacking and tax breakdown. The four-tier...",
    "searchText": "step 4: discover a product and read its price developer onboarding the buyer agent queries the layer 1 mcp tool get live sku quote and receives a dynamic quote with automated discount stacking and tax breakdown. the four-tier discount pipeline 1. tier 1: volume discount : basis points based on requested quantity. 2. tier 2: campaign promo : a percentage off, optionally capped. 3. tier 3: upi rail incentive : a flat cashback on the upi circle rail. 4. tier 4: promo code : a further percentage off when the agent passes a code the merchant honours. all four are the merchant's to set. tiers 1 is authored per sku as volumetiers , and tiers 2-4 as merchantoffers — both from the merchant sku studio's offers & promo codes panel, or by posting them on the listing. a sku that carries merchantoffers states its offers completely , so leaving the campaign out there means no campaign rather than falling back to a default. a sku with no merchantoffers gets the mesh's demo defaults instead: a 10% campaign capped at ₹20.00, ₹1.50 of upi cashback, and the corp 5pct code at 5% off. ---"
  },
  {
    "route": "/docs/onboarding#step-5-clear-the-proof-of-work-and-bargain",
    "docTitle": "Developer onboarding",
    "headingText": "Step 5: Clear the proof of work and bargain",
    "snippet": "If the SKU requires dynamic negotiation, the gateway challenges the buyer with an HTTP 402 Payment Required status containing a cryptographic SHA-256...",
    "searchText": "step 5: clear the proof of work and bargain developer onboarding if the sku requires dynamic negotiation, the gateway challenges the buyer with an http 402 payment required status containing a cryptographic sha-256 proof-of-work puzzle. ---"
  },
  {
    "route": "/docs/onboarding#step-6-reserve-stock",
    "docTitle": "Developer onboarding",
    "headingText": "Step 6: Reserve stock",
    "snippet": "The buyer locks stock for 60 seconds via reserve inventory lock . The enclave executes an atomic Redis Lua script, returning a lock token and monotonic fencing...",
    "searchText": "step 6: reserve stock developer onboarding the buyer locks stock for 60 seconds via reserve inventory lock . the enclave executes an atomic redis lua script, returning a lock token and monotonic fencing token: ---"
  },
  {
    "route": "/docs/onboarding#step-7-sign-the-cart-and-execution-mandates",
    "docTitle": "Developer onboarding",
    "headingText": "Step 7: Sign the cart and execution mandates",
    "snippet": "---",
    "searchText": "step 7: sign the cart and execution mandates developer onboarding ---"
  },
  {
    "route": "/docs/onboarding#step-8-settle",
    "docTitle": "Developer onboarding",
    "headingText": "Step 8: Settle",
    "snippet": "The buyer agent submits the mandate chain to POST /api/v1/settlement/execute . ---",
    "searchText": "step 8: settle developer onboarding the buyer agent submits the mandate chain to post /api/v1/settlement/execute . ---"
  },
  {
    "route": "/docs/onboarding#runnable-end-to-end-examples",
    "docTitle": "Developer onboarding",
    "headingText": "Runnable end-to-end examples",
    "snippet": "Two complete programs build and verify a full mandate chain, one per runtime: Neither touches the network -- signing and hash-chaining are local Ed25519...",
    "searchText": "runnable end-to-end examples developer onboarding two complete programs build and verify a full mandate chain, one per runtime: neither touches the network -- signing and hash-chaining are local ed25519 operations -- so both run against nothing but the sdk: that command compiles both, runs both, and fails if either drifts from the snippets embedded in these docs. it is the reason the code below is trustworthy: it is not a transcription, it is the program. here is the last step of each -- recomputing the hashes and checking that the chain the buyer signed is the chain the merchant priced: the buyer sdk guide walks the same chain stage by stage, with the discovery, negotiation, locking and settlement calls that surround it. ---"
  },
  {
    "route": "/docs/onboarding#errors-and-troubleshooting",
    "docTitle": "Developer onboarding",
    "headingText": "Errors and troubleshooting",
    "snippet": "",
    "searchText": "errors and troubleshooting developer onboarding "
  },
  {
    "route": "/docs/onboarding#status-codes",
    "docTitle": "Developer onboarding",
    "headingText": "Status codes",
    "snippet": "HTTP Code Error Condition Root Cause & Resolution --- --- --- 400 Bad Request InvalidGstinException GSTIN fails Indian Luhn Mod-36 checksum. Verify format...",
    "searchText": "status codes developer onboarding http code error condition root cause & resolution --- --- --- 400 bad request invalidgstinexception gstin fails indian luhn mod-36 checksum. verify format 27aaacg0123m1z5 . 400 bad request budgetexceededviolation cart total exceeds the intent mandate's maxbudgetpaise . raise the delegated budget, or bargain the price down. 400 bad request signatureverificationfailedexception ed25519 signature invalid over rfc 8785 canonical bytes. re-check signing key and payload canonicalizer. 402 payment required http402requirederror ingress pow challenge or micro-escrow debit required. ensure sdk has autosolvepow=true . 404 not found catalognotfoundexception requested skuid does not exist for the specified merchantdid . 409 conflict noncereplayexception the execution mandate's nonce was already spent, or its timestamp fell outside the accepted window of 5s behind to 60s ahead. 409 conflict insufficientstockexception inventory count is below requested quantity. intercept and route to vector healer. 502 bad gateway settlementcompensationtriggeredexception razorpay route split payout failed. automatic lifo rollback was executed and queued to dlq."
  },
  {
    "route": "/docs/onboarding#common-failures",
    "docTitle": "Developer onboarding",
    "headingText": "Common failures",
    "snippet": "\"Nonce replay detected or timestamp drift\" - Cause : Server timestamp and client timestamp differ by more than 5 seconds in the past or 60 seconds in the...",
    "searchText": "common failures developer onboarding \"nonce replay detected or timestamp drift\" - cause : server timestamp and client timestamp differ by more than 5 seconds in the past or 60 seconds in the future. - fix : synchronize client host clocks using ntp ( sudo apt install chrony && chronyd -q ). \"floating point values rejected in jcs canonicalizer\" - cause : monetary inputs contain floats (e.g. 99.50 instead of 9950 ). - fix : pass all prices, taxes, and discounts as integer paise -- the arithmetic enclave accepts nothing else. \"stalepricequoteexception: price quote is stale\" - cause : dynamic bullion quote exceeded its maxquotettlseconds (default 60s). - fix : call get live sku quote again immediately before building the cart and execution mandates."
  },
  {
    "route": "/docs/buyer-sdk",
    "docTitle": "Buyer SDK",
    "headingText": "",
    "snippet": "For developers building the buyer side: an agent that discovers a product, agrees a price, reserves stock, signs an AP2 mandate chain and settles -- without a...",
    "searchText": " buyer sdk for developers building the buyer side: an agent that discovers a product, agrees a price, reserves stock, signs an ap2 mandate chain and settles -- without a human at a checkout. the typescript and python clients expose the same protocol, and the last section lists every place they differ. every snippet on this page is checked against the sdk's generated symbol table by npm run docs:verify , run locally -- this repository has no ci by design, so the checks are commands a person runs. a method, constructor argument or service port named here that the sdk does not have fails that command. link targets are checked separately by python scripts/verifydoclinks.py --check , because docs:verify reads snippets and not links. ---"
  },
  {
    "route": "/docs/buyer-sdk#installation",
    "docTitle": "Buyer SDK",
    "headingText": "Installation",
    "snippet": "Install the standalone buyer agent SDK for your target runtime: ---",
    "searchText": "installation buyer sdk install the standalone buyer agent sdk for your target runtime: ---"
  },
  {
    "route": "/docs/buyer-sdk#client-setup-and-keys",
    "docTitle": "Buyer SDK",
    "headingText": "Client setup and keys",
    "snippet": "The client takes a key manager and the addresses of the mesh services it talks to. There is no single base URL: quotes and locks come from the MCP Server,...",
    "searchText": "client setup and keys buyer sdk the client takes a key manager and the addresses of the mesh services it talks to. there is no single base url: quotes and locks come from the mcp server, settlement from the mandate engine, and http 402 micro-metering from the x402 gateway. the python client groups the same addresses on a meshslaconfig rather than on the client itself, and its key manager is constructed from a private key hex: the budget ceiling is not a client setting in either runtime. it is a field of the intent mandate ( maxbudgetpaise ), signed by the human principal — see signing the chain — so the limit travels with the authorization instead of living in the agent's own configuration, where the agent could change it. ---"
  },
  {
    "route": "/docs/buyer-sdk#the-ap2-mandate-chain",
    "docTitle": "Buyer SDK",
    "headingText": "The AP2 mandate chain",
    "snippet": "Every transaction executes across a cryptographic mandate chain: ---",
    "searchText": "the ap2 mandate chain buyer sdk every transaction executes across a cryptographic mandate chain: ---"
  },
  {
    "route": "/docs/buyer-sdk#quotes-and-discounts",
    "docTitle": "Buyer SDK",
    "headingText": "Quotes and discounts",
    "snippet": "A quote prices one SKU at one quantity for one delivery pincode, with the discount tiers already stacked and the GST already split. The quoteHash it returns is...",
    "searchText": "quotes and discounts buyer sdk a quote prices one sku at one quantity for one delivery pincode, with the discount tiers already stacked and the gst already split. the quotehash it returns is what the inventory lock is bound to. verifyshippingsla is typescript-only; from python, call the sla route on the mcp server directly. the casing split is not arbitrary. python transport models are snake case because they follow the mcp tool schema, while mandate models are camelcase in both languages because field names are inside the bytes that get signed -- see where the two runtimes diverge before renaming anything. ---"
  },
  {
    "route": "/docs/buyer-sdk#negotiation-and-amendments",
    "docTitle": "Buyer SDK",
    "headingText": "Negotiation and amendments",
    "snippet": "Negotiation is bounded by construction rather than by convention: the SDK ships the turn ceiling and the per-turn micro-fee as constants, so a client cannot...",
    "searchText": "negotiation and amendments buyer sdk negotiation is bounded by construction rather than by convention: the sdk ships the turn ceiling and the per-turn micro-fee as constants, so a client cannot quietly bargain forever. a concession arrives as a price-drop alert. applying one produces a dual-signed amendment mandate rather than mutating the cart, which is what keeps concessions monotonic: the amendment records the previous cart's hash and a signed pricedeltapaise , so a later round cannot walk the price back up without leaving a broken chain behind it. the python client's handlepricedropalert is a different method with the same name: it registers an alert with the mcp server and returns the registration, and registerpricedropalert is an alias for it. amendment mandates are constructed there with createsignedamendmentmandate . ---"
  },
  {
    "route": "/docs/buyer-sdk#signing-the-chain",
    "docTitle": "Buyer SDK",
    "headingText": "Signing the chain",
    "snippet": "The buyer agent signs exactly one link of the chain: the Execution Mandate. The Intent Mandate is signed by the human principal's key and the Cart Mandate by...",
    "searchText": "signing the chain buyer sdk the buyer agent signs exactly one link of the chain: the execution mandate. the intent mandate is signed by the human principal's key and the cart mandate by the merchant's, which is why each helper takes its signer as a separate argument rather than reading one off the client. the three snippets below are not written out here. they are regions of examples/typescript/mandatechain.ts and examples/python/mandatechain.py , two standalone programs that python scripts/verifyexamples.py --check compiles and then runs . neither touches the network — signing and hash-chaining are local ed25519 operations — so the whole mandate chain is exercised without a single service running, and this page cannot drift from code that is proven to work. the intent mandate carries the budget ceiling, signed by the human principal. the limit travels with the authorization rather than living in the agent's own configuration, where the agent could change it. the python helper takes the same fields as flat keyword arguments and the signer as userkeymanager , where typescript takes a params object and a positional signer. the cart mandate arrives over the wire from the merchant enclave; the buyer agent verifies it rather than producing one. it is shown here because the example has to build one to have a chain to verify, and because it is where the gst split is fixed — equal cgstpaise and sgstpaise when the merchant and the buyer are in the same state, the whole amount in igstpaise when they are not. then the one link the buyer agent signs: createsignedexecutionmandate records the sha-256 of each preceding mandate in intentmandatehash and cartmandatehash . that is what makes the chain verifiable rather than merely signed: a cart edited after the user authorized it no longer hashes to the value the execution mandate was signed over, and recomputation catches it without needing to have seen the original. ---"
  },
  {
    "route": "/docs/buyer-sdk#verifying-the-chain",
    "docTitle": "Buyer SDK",
    "headingText": "Verifying the chain",
    "snippet": "Verification recomputes both hashes and compares them with what the execution mandate recorded. The examples do it twice — once on the chain as signed, once on...",
    "searchText": "verifying the chain buyer sdk verification recomputes both hashes and compares them with what the execution mandate recorded. the examples do it twice — once on the chain as signed, once on a cart discounted after the fact — and exit non-zero if the second one ever passes. this is the part worth reading twice, because the two runtimes do not have the same contract here: typescript's verifymandatechain is declared = boolean but only ever returns true or throws mandateverificationerror ; it never returns false . so if (!verifymandatechain(...)) compiles, type-checks, and silently never runs its else branch — catch the error instead of testing the result. python's verifymandatehashchain takes raiseonmismatch , which defaults to true but can be set to false for a genuine boolean. running either program prints the two hashes, then verified and rejected , and exits non-zero if that ever inverts: ---"
  },
  {
    "route": "/docs/buyer-sdk#inventory-locks-and-fencing-tokens",
    "docTitle": "Buyer SDK",
    "headingText": "Inventory locks and fencing tokens",
    "snippet": "Reserve stock against the quote, with a monotonic fencing token so a lock that expired mid-flight cannot be used to settle later: The lock route is metered...",
    "searchText": "inventory locks and fencing tokens buyer sdk reserve stock against the quote, with a monotonic fencing token so a lock that expired mid-flight cannot be used to settle later: the lock route is metered under http 402. both clients solve the proof-of-work challenge for you — the python client only while autosolvepow is left on in meshslaconfig . ---"
  },
  {
    "route": "/docs/buyer-sdk#settlement",
    "docTitle": "Buyer SDK",
    "headingText": "Settlement",
    "snippet": "Submit the whole mandate chain to the Mandate Engine for the four-way split transfer. This is the final step of the happyPath scenario, described below by the...",
    "searchText": "settlement buyer sdk submit the whole mandate chain to the mandate engine for the four-way split transfer. this is the final step of the happypath scenario, described below by the driver that runs it: the typescript client also exposes executeautonomouspurchase , which takes the same mandates plus a skuid and quantity and runs quote, lock and settlement as one call. it is the convenience path; the sections above are what it does internally, and are what you want when a step needs to be inspected or retried on its own. ---"
  },
  {
    "route": "/docs/buyer-sdk#where-the-two-runtimes-diverge",
    "docTitle": "Buyer SDK",
    "headingText": "Where the two runtimes diverge",
    "snippet": "The two SDKs are not mirror images, and pretending otherwise is how people write code that typechecks and then fails in production. The divergences fall into...",
    "searchText": "where the two runtimes diverge buyer sdk the two sdks are not mirror images, and pretending otherwise is how people write code that typechecks and then fails in production. the divergences fall into three groups, and only the first is deliberate."
  },
  {
    "route": "/docs/buyer-sdk#field-casing-and-the-one-rule-you-must-not-clean-up",
    "docTitle": "Buyer SDK",
    "headingText": "Field casing, and the one rule you must not \"clean up\"",
    "snippet": "Mandate models are camelCase in both languages, and that is load-bearing. Signing canonicalizes the mandate to JCS — keys sorted, then serialized whole — so...",
    "searchText": "field casing, and the one rule you must not \"clean up\" buyer sdk mandate models are camelcase in both languages, and that is load-bearing. signing canonicalizes the mandate to jcs — keys sorted, then serialized whole — so the field names are inside the bytes that get hashed and signed ( jcscanonicalizer.ts , agentkeymanager.canonicalizejson ). rename maxbudgetpaise to max budget paise on the python side and the canonical json changes, the sha-256 changes, and intentmandatehash computed in python stops matching the one computed in typescript. cross-language chain verification breaks silently — the code still runs, the signature still validates locally, and only a mixed-language settlement fails. so: mandatemodels.py is camelcase on purpose. leave it. transport models are the opposite, and they have to face both ways. the mcp tool layer speaks snake case; the mcp http face the sdks actually call speaks camelcase, converting in wiremappers.tosdkskuquote . so transportmodels.py keeps snake case field names and carries a to camel alias generator with populate by name , which lets it parse the camelcase wire while quote.quote hash keeps working. nothing here is canonicalized or signed, so the dual spelling costs nothing but the surprise."
  },
  {
    "route": "/docs/buyer-sdk#names-that-mean-the-same-thing",
    "docTitle": "Buyer SDK",
    "headingText": "Names that mean the same thing",
    "snippet": "Neither spelling is more correct; they are accidents of two codebases growing in parallel. Renaming either side is a breaking change for anyone already on it,...",
    "searchText": "names that mean the same thing buyer sdk neither spelling is more correct; they are accidents of two codebases growing in parallel. renaming either side is a breaking change for anyone already on it, so they are recorded instead: typescript python what it is --- --- --- getbuyerkeymanager getkeymanager the client's own signer agentkeymanager.fromsecretkey agentkeymanager.fromprivatekeyhex construct from a key getsecretkeyhex getprivatekeyhex read the key back verifymandatechain verifymandatehashchain check the chain (see verifying the chain — the contracts differ too) solvepowchallenge solvepowchallenge solve the http 402 challenge verifypowsolution verifypowsolution check a solution formatagentdid formatdid render a did:agent: string generateagentkeypair generatekeypair fresh ed25519 pair agentkeypair agentkeypair the pair itself cartitem / taxbreakdown cartitemschema / taxbreakdownschema cart line and tax split mandateverificationerror mandatevalidationerror raised on a broken chain python additionally exports an exception alias beside most error names; they are the same class."
  },
  {
    "route": "/docs/buyer-sdk#capabilities-only-one-side-has",
    "docTitle": "Buyer SDK",
    "headingText": "Capabilities only one side has",
    "snippet": "verifyShippingSla is TypeScript-only — from Python, call the SLA route on the MCP server directly. Python has AgentMandateBuilder , PowSolver and...",
    "searchText": "capabilities only one side has buyer sdk verifyshippingsla is typescript-only — from python, call the sla route on the mcp server directly. python has agentmandatebuilder , powsolver and validatemandateinvariants with no typescript equivalent, and models the x402 escrow flow ( escrowsession , escrowrefundreceipt ) that typescript does not expose."
  },
  {
    "route": "/docs/buyer-sdk#the-routes-both-clients-call",
    "docTitle": "Buyer SDK",
    "headingText": "The routes both clients call",
    "snippet": "Both SDKs now target the same four routes: /api/v1/quote , /api/v1/lock and /api/v1/sla on the MCP server, and /api/v1/settlement/execute on the Mandate...",
    "searchText": "the routes both clients call buyer sdk both sdks now target the same four routes: /api/v1/quote , /api/v1/lock and /api/v1/sla on the mcp server, and /api/v1/settlement/execute on the mandate engine. that is worth stating because it was not true until recently. the python client asked for /api/v1/quotes/live and /api/v1/inventory/lock , which nothing served, and posted the quote where the adapter expects a get . every such call failed against a running mesh while the sdk's own suite stayed green, because it mocks the transport, and its test asserted the wrong path as though that were the contract. test/sdkendpointparity.test.ts in the dashboard now compares every endpoint constant in both sdks against the routes the servers declare, reading both sides from source and mocking nothing."
  },
  {
    "route": "/docs/buyer-sdk#defaults-that-match",
    "docTitle": "Buyer SDK",
    "headingText": "Defaults that match",
    "snippet": "Both SDKs share defaultLockTtlSeconds = 60 , matching the MCP server's own default ( packages/mcpServer/src/constants/protocolConstants.ts:53 ). This is the...",
    "searchText": "defaults that match buyer sdk both sdks share defaultlockttlseconds = 60 , matching the mcp server's own default ( packages/mcpserver/src/constants/protocolconstants.ts:53 ). this is the hold window for inventory locks; both sdks call the same /api/v1/lock endpoint, so the duration must agree."
  },
  {
    "route": "/docs/merchant-guide",
    "docTitle": "Merchant guide",
    "headingText": "",
    "snippet": "For merchants putting inventory somewhere an agent can buy it. By the end you will have a registered identity, a published catalog an agent can search, and...",
    "searchText": " merchant guide for merchants putting inventory somewhere an agent can buy it. by the end you will have a registered identity, a published catalog an agent can search, and prices that respond to order quantity and to the bullion spot rate. bargaining is configured separately and is off until you turn it on -- see the negotiation policy. ---"
  },
  {
    "route": "/docs/merchant-guide#merchant-identity",
    "docTitle": "Merchant guide",
    "headingText": "Merchant identity",
    "snippet": "Every merchant on RazorAgent Mesh is identified by an immutable Decentralized Identifier ( did:razoragent:merchant: ) derived from an Ed25519 cryptographic...",
    "searchText": "merchant identity merchant guide every merchant on razoragent mesh is identified by an immutable decentralized identifier ( did:razoragent:merchant: ) derived from an ed25519 cryptographic public key. you do not send a public key. the server generates the ed25519 keypair, derives the did from it, and returns both on the merchantprofile -- so read publickeyhex off the response rather than choosing one."
  },
  {
    "route": "/docs/merchant-guide#validation-rules",
    "docTitle": "Merchant guide",
    "headingText": "Validation rules",
    "snippet": "- The request model forbids unknown fields. All five above are required and anything else is a 422 . - GSTIN : the 15-character identifier is checked against...",
    "searchText": "validation rules merchant guide - the request model forbids unknown fields. all five above are required and anything else is a 422 . - gstin : the 15-character identifier is checked against the statutory luhn mod-36 checksum, not just the pattern. - razorpay route account : must match acc [a-za-z0-9 ]+ , because it is the destination of a real split transfer. - origin pincode : a 6-digit indian pincode. place of supply is decided from it, so it decides whether a sale is taxed cgst + sgst or igst. ---"
  },
  {
    "route": "/docs/merchant-guide#publishing-a-catalog",
    "docTitle": "Merchant guide",
    "headingText": "Publishing a catalog",
    "snippet": "RazorAgent Mesh supports 4 ingestion adapters for populating and vectorizing merchant catalogs: The single-SKU route is abbreviated above to fit the diagram....",
    "searchText": "publishing a catalog merchant guide razoragent mesh supports 4 ingestion adapters for populating and vectorizing merchant catalogs: the single-sku route is abbreviated above to fit the diagram. in full it is post /api/v1/merchant/{merchantdid}/catalog -- the merchant did is part of the path, not a header, so a catalog write is always scoped to one merchant."
  },
  {
    "route": "/docs/merchant-guide#volume-tiers",
    "docTitle": "Merchant guide",
    "headingText": "Volume tiers",
    "snippet": "Merchants can define tiered volume discount curves in Basis Points (1 BPS = 0.01%): ---",
    "searchText": "volume tiers merchant guide merchants can define tiered volume discount curves in basis points (1 bps = 0.01%): ---"
  },
  {
    "route": "/docs/merchant-guide#bullion-pricing",
    "docTitle": "Merchant guide",
    "headingText": "Bullion pricing",
    "snippet": "For gold and silver precious metals, pricing is calculated dynamically from the live MCX Spot Oracle with a 5-second cache: Bullion Spot Formula:...",
    "searchText": "bullion pricing merchant guide for gold and silver precious metals, pricing is calculated dynamically from the live mcx spot oracle with a 5-second cache: bullion spot formula: unitpricepaise = ⌊(spotpergrampaise × puritycarats) / 24⌋ × weightgrams + makingchargespaise ---"
  },
  {
    "route": "/docs/merchant-guide#domain-facets",
    "docTitle": "Merchant guide",
    "headingText": "Domain facets",
    "snippet": "Catalogs support specialized industry facets with custom attribute normalization: Industry Domain Key Schema Attributes Example Payload --- --- --- Jewelry...",
    "searchText": "domain facets merchant guide catalogs support specialized industry facets with custom attribute normalization: industry domain key schema attributes example payload --- --- --- jewelry purity ( 18k / 22k / 24k ), weight (g), making charges {\"purity\": \"22k\", \"weightgrams\": 10.5} apparel size ( s / m / l / xl ), color, fabric, gsm {\"size\": \"l\", \"fabric\": \"cotton\", \"gsm\": 220} pharma active molecule, schedule class, expiry batch {\"molecule\": \"paracetamol\", \"dosage\": \"650mg\"} fmcg net weight, shelf life, organic certification {\"shelflifedays\": 180, \"organic\": true} ---"
  },
  {
    "route": "/docs/merchant-guide#hsn-codes-and-tax-rates",
    "docTitle": "Merchant guide",
    "headingText": "HSN codes and tax rates",
    "snippet": "Every SKU maps to an official Indian Harmonized System of Nomenclature (HSN) chapter: HSN Code Chapter Category GST Rate Statutory Split --- --- --- --- 7113...",
    "searchText": "hsn codes and tax rates merchant guide every sku maps to an official indian harmonized system of nomenclature (hsn) chapter: hsn code chapter category gst rate statutory split --- --- --- --- 7113 gold & precious jewelry 3.0% 1.5% cgst + 1.5% sgst (or 3.0% igst) 6109 cotton & knitted apparel 5.0% 2.5% cgst + 2.5% sgst (or 5.0% igst) 3004 essential pharmaceuticals 5.0% 2.5% cgst + 2.5% sgst (or 5.0% igst) 8471 computing & electronics 18.0% 9.0% cgst + 9.0% sgst (or 18.0% igst) ---"
  },
  {
    "route": "/docs/merchant-guide#how-you-find-out-an-order-happened",
    "docTitle": "Merchant guide",
    "headingText": "How you find out an order happened",
    "snippet": "There is no order email, SMS or merchant callback. A sale reaches you through the same Server-Sent Events bus the dashboard reads: GET /api/v1/telemetry/stream...",
    "searchText": "how you find out an order happened merchant guide there is no order email, sms or merchant callback. a sale reaches you through the same server-sent events bus the dashboard reads: get /api/v1/telemetry/stream on the mandate engine (port 8000), where inventory locked says your stock was committed and payment captured says the money moved, carrying the four route transfer legs and the gstr-1 invoice hash. two things to know before you write the consumer, because neither is where you would look first: - no event carries merchantdid . filter payment captured on payload.transfers[].recipientaccountid -- the razorpayaccountid you registered above -- and inventory locked on payload.skuid against your own catalog. - sessionid does not join the two halves. the engine puts the payment id in that field on payment captured , so group on the payment id instead. merchant-side subscribers has the working listener, the lifecycle events in order, and what is not built -- there is no outbound order notification, and the inbound razorpay receiver acknowledges a verified delivery without reconciling anything against it -- stated plainly so you do not design around something that is not there."
  },
  {
    "route": "/docs/tool-reference",
    "docTitle": "MCP tool reference",
    "headingText": "",
    "snippet": "{/ GENERATED FILE -- do not edit by hand. Produced by scripts/generateToolReference.ts from packages/mcpServer/src/constants/ Manifest.ts, which is the same...",
    "searchText": " mcp tool reference {/ generated file -- do not edit by hand. produced by scripts/generatetoolreference.ts from packages/mcpserver/src/constants/ manifest.ts, which is the same json schema an agent receives from tools/list. change the manifest, then run npm run docs:tools . /} the complete surface an autonomous buyer can call. these 10 tools are what tools/list returns; the tables below are generated from that same schema, so an argument documented here is an argument the server will accept, and a constraint shown here is one it will enforce."
  },
  {
    "route": "/docs/tool-reference#transport",
    "docTitle": "MCP tool reference",
    "headingText": "Transport",
    "snippet": "The server speaks MCP over Streamable HTTP. --- --- Endpoint http://localhost:4001/mcp Protocol MCP over Streamable HTTP (JSON-RPC 2.0) Session Issued by the...",
    "searchText": "transport mcp tool reference the server speaks mcp over streamable http. --- --- endpoint http://localhost:4001/mcp protocol mcp over streamable http (json-rpc 2.0) session issued by the server on initialize; sent back as mcp-session-id auth none in local mode. the mesh authenticates the mandate chain , not the caller a rest adapter mirrors the read-only discovery tools at /api/v1/ for clients that do not speak mcp. it is the same handler and the same telemetry; see the telemetry & sse guide."
  },
  {
    "route": "/docs/tool-reference#calling-a-tool",
    "docTitle": "MCP tool reference",
    "headingText": "Calling a tool",
    "snippet": "Arguments are snake case on the wire. The server also accepts camelCase aliases for the buyer SDK's benefit, but the manifest names below are the canonical...",
    "searchText": "calling a tool mcp tool reference arguments are snake case on the wire. the server also accepts camelcase aliases for the buyer sdk's benefit, but the manifest names below are the canonical ones."
  },
  {
    "route": "/docs/tool-reference#l1--discovery",
    "docTitle": "MCP tool reference",
    "headingText": "L1 · Discovery",
    "snippet": "Find something to buy and get a price for it. Every quote is sealed with an HMAC hash that a later stage must present, so a cart cannot be built from a price...",
    "searchText": "l1 · discovery mcp tool reference find something to buy and get a price for it. every quote is sealed with an hmac hash that a later stage must present, so a cart cannot be built from a price the mesh never issued."
  },
  {
    "route": "/docs/tool-reference#search_catalog",
    "docTitle": "MCP tool reference",
    "headingText": "search_catalog",
    "snippet": "Finds catalog products matching a natural-language description, ranked by semantic similarity. Use this first when the buyer describes what they want rather...",
    "searchText": "search_catalog mcp tool reference finds catalog products matching a natural-language description, ranked by semantic similarity. use this first when the buyer describes what they want rather than naming a sku id. the response reports embedding mode: when it is 'hash' the ranking is not semantic and the order is not meaningful. a result whose merchant has a sale scheduled carries next promotion, with its start time and expected savings paise. if any result carries one you must say so in your final answer -- naming the sku, the saving and when it starts -- even for a product you did not buy and even when the buyer did not ask about discounts. a buyer who spends money hours before a sale they were shown, and were not told about, has been failed by their agent."
  },
  {
    "route": "/docs/tool-reference#search_catalog-arguments",
    "docTitle": "MCP tool reference",
    "headingText": "search_catalog arguments",
    "snippet": "Parameter Type Required Description --- --- --- --- query text string Yes Plain-language description of the desired product. 'queryText' and 'query' are...",
    "searchText": "search_catalog arguments mcp tool reference parameter type required description --- --- --- --- query text string yes plain-language description of the desired product. 'querytext' and 'query' are accepted as aliases for this field. (length 1–500) limit integer no maximum number of ranked results to return. (1–25; defaults to 5 )"
  },
  {
    "route": "/docs/tool-reference#browse_catalog",
    "docTitle": "MCP tool reference",
    "headingText": "browse_catalog",
    "snippet": "Lists what the mesh actually sells, with optional category, brand, HSN and stock filters. Use this when search catalog returns nothing useful, or when you want...",
    "searchText": "browse_catalog mcp tool reference lists what the mesh actually sells, with optional category, brand, hsn and stock filters. use this when search catalog returns nothing useful, or when you want to see the range before choosing -- it enumerates the live catalog directly rather than ranking it, so a product missing from the semantic index still appears here. returns total matching so you can page with offset, and categories available so you can widen a filter that matched nothing. prices are list prices: call get live sku quote for a binding number. each item also carries next promotion when its merchant has a sale scheduled, with the start time and expected savings paise -- so you can find what is about to get cheaper without quoting every sku. filter with has upcoming promotion to ask that question directly, and advise your buyer to wait when the saving is worth the delay. available stock, and the min stock filter applied to it, are both read after reservations whose lock has lapsed are released -- so a sku an abandoned lock was holding is listed again rather than staying hidden behind a hold nobody is using."
  },
  {
    "route": "/docs/tool-reference#browse_catalog-arguments",
    "docTitle": "MCP tool reference",
    "headingText": "browse_catalog arguments",
    "snippet": "Parameter Type Required Description --- --- --- --- brand string No Exact brand, case-insensitive. (length 1–∞) category string No Exact category,...",
    "searchText": "browse_catalog arguments mcp tool reference parameter type required description --- --- --- --- brand string no exact brand, case-insensitive. (length 1–∞) category string no exact category, case-insensitive. (length 1–∞) has upcoming promotion boolean no omit to list everything. true lists only skus with a sale scheduled; false only those without one, which is what to buy when waiting is not an option. hsn code string no exact hsn tax code, as printed on the invoice line (94013000 is seating). use it to list everything taxed alike. (length 1–∞) limit integer no how many items to return in this page. (1–100; defaults to 25 ) min stock integer no defaults to 1, so only orderable stock is listed. pass 0 to include out-of-stock. (min 0; defaults to 1 ) offset integer no how many items to skip, for paging. compare with total matching in the response to know when you have seen everything. (min 0; defaults to 0 )"
  },
  {
    "route": "/docs/tool-reference#get_live_sku_quote",
    "docTitle": "MCP tool reference",
    "headingText": "get_live_sku_quote",
    "snippet": "Calculates real-time unit pricing, volume discount tiers, and HSN-compliant GST for a requested SKU and volume. A merchant sale that is RUNNING is already in...",
    "searchText": "get_live_sku_quote mcp tool reference calculates real-time unit pricing, volume discount tiers, and hsn-compliant gst for a requested sku and volume. a merchant sale that is running is already in offered unit price paise and is named in applied discounts as scheduled promotion. a sale that has not started yet is in upcoming promotions, with its start time and expected savings paise. if upcoming promotions is non-empty you must tell the buyer the sale exists, what it would save and when it starts, even if you go on to recommend buying now -- a buyer who later discovers you bought hours before a sale you saw and did not mention has been badly served. say it in your final answer, not only in your reasoning. which campaign, cashback and promo codes apply is set per sku by its merchant, so a code that discounts one sku may do nothing on another -- applied discounts names every one that fired. available stock is what reserve inventory lock would grant you at this moment: reservations whose lock has already lapsed are released before the count is taken, so the number you read here and the number the lock enforces are the same one."
  },
  {
    "route": "/docs/tool-reference#get_live_sku_quote-arguments",
    "docTitle": "MCP tool reference",
    "headingText": "get_live_sku_quote arguments",
    "snippet": "Parameter Type Required Description --- --- --- --- buyer agent id string Yes Your agent DID. Under mesh demo custodial custody it is minted by establish agent...",
    "searchText": "get_live_sku_quote arguments mcp tool reference parameter type required description --- --- --- --- buyer agent id string yes your agent did. under mesh demo custodial custody it is minted by establish agent delegation, so call that first and reuse the buyer agent did it returns rather than inventing one. (matches ^did:agent:[a-z0-9 \\-\\.:]+$ ) delivery pincode string yes six-digit destination pin code. it selects the courier zone and the gst treatment, so a quote for one address does not hold for another. (matches ^[1-9][0-9]{5}$ ) quantity integer yes units to price. volume tiers are applied from this number, so quoting 1 and then buying 10 gives the wrong price. (1–10000) sku id string yes the sku to price, exactly as search catalog or browse catalog returned it. (matches ^sku-[a-z0-9 -]{3,32}$ ) promo code string no optional merchant promo code. codes are set per sku, so one that discounts another sku may do nothing here; applied discounts names whatever actually fired."
  },
  {
    "route": "/docs/tool-reference#verify_shipping_sla",
    "docTitle": "MCP tool reference",
    "headingText": "verify_shipping_sla",
    "snippet": "Deterministically calculates courier routing zone, delivery SLA hours, and shipping cost. CHECK serviceable before building a cart: it is false when no courier...",
    "searchText": "verify_shipping_sla mcp tool reference deterministically calculates courier routing zone, delivery sla hours, and shipping cost. check serviceable before building a cart: it is false when no courier serves the delivery pincode, and when the tier you asked for is not offered to that zone. both cases return unserviceable reason to relay to your buyer, and available delivery tiers so you can re-request usefully. create cart mandate refuses an unserviceable address outright."
  },
  {
    "route": "/docs/tool-reference#verify_shipping_sla-arguments",
    "docTitle": "MCP tool reference",
    "headingText": "verify_shipping_sla arguments",
    "snippet": "Parameter Type Required Description --- --- --- --- delivery pincode string Yes Six-digit PIN code the goods ship TO. (matches ^[1-9][0-9]{5}$ ) origin pincode...",
    "searchText": "verify_shipping_sla arguments mcp tool reference parameter type required description --- --- --- --- delivery pincode string yes six-digit pin code the goods ship to. (matches ^[1-9][0-9]{5}$ ) origin pincode string yes six-digit pin code the goods ship from -- the merchant warehouse, not the buyer. it is the origin of the courier zone calculation. (matches ^[1-9][0-9]{5}$ ) package weight grams integer yes billable package weight in grams. shipping is priced in weight slabs, so this changes the cost even when the zone does not. (min 1) required delivery tier string yes service level to price. not every tier is offered to every zone: when one is not, serviceable comes back false and available delivery tiers lists what is. (one of standard , express , sameday )"
  },
  {
    "route": "/docs/tool-reference#l2--negotiation",
    "docTitle": "MCP tool reference",
    "headingText": "L2 · Negotiation",
    "snippet": "Bargain against the merchant's own policy. Each turn is metered by an x402-INR micro-escrow, which is what stops a bidding loop from being free to run.",
    "searchText": "l2 · negotiation mcp tool reference bargain against the merchant's own policy. each turn is metered by an x402-inr micro-escrow, which is what stops a bidding loop from being free to run."
  },
  {
    "route": "/docs/tool-reference#negotiate_price",
    "docTitle": "MCP tool reference",
    "headingText": "negotiate_price",
    "snippet": "Bargains for a lower unit price by running a full x402-INR alternating-offer negotiation against the merchant gateway -- up to 5 turns, each gated by a...",
    "searchText": "negotiate_price mcp tool reference bargains for a lower unit price by running a full x402-inr alternating-offer negotiation against the merchant gateway -- up to 5 turns, each gated by a proof-of-work solve and charged ₹0.50 from a micro-escrow this tool opens and releases for you. negotiation is opt-in per merchant: many sell at a firm listed price and answer status declined, which costs nothing and means buy at list rather than retry. the merchant also sets the floor, so a converged price is theirs to allow, not yours to name. give it what you want to open at and, in max unit price paise, the most you will pay: the bid ladder never crosses that ceiling, so a converged result is always affordable. worth a call before get live sku quote on anything expensive; skip it on cheap items, where the turn fees can exceed the saving (the response reports both, so you can tell). a converged price binds: quote the same sku with the same buyer agent id and quantity within 5 minutes and get live sku quote applies it as a negotiated line, so the cart and the settlement charge it. read savings realised paise, not savings vs list paise, when you tell the buyer what the bargaining saved: the first is measured against the discounts they would have got anyway, and the second double-counts them."
  },
  {
    "route": "/docs/tool-reference#negotiate_price-arguments",
    "docTitle": "MCP tool reference",
    "headingText": "negotiate_price arguments",
    "snippet": "Parameter Type Required Description --- --- --- --- buyer agent id string Yes Your agent DID, the same one you quoted with. (matches ^did:agent:[a-z0-9...",
    "searchText": "negotiate_price arguments mcp tool reference parameter type required description --- --- --- --- buyer agent id string yes your agent did, the same one you quoted with. (matches ^did:agent:[a-z0-9 \\-\\.:]+$ ) max unit price paise integer yes your walk-away price per unit. a hard ceiling, not a target: no turn will bid above it. (min 1) opening bid paise integer yes your opening offer per unit. below the list price, or there is nothing to negotiate. (min 1) quantity integer yes units you intend to buy. volume moves the merchant floor, so a larger order can settle lower per unit. (1–10000) sku id string yes the sku to bargain over. (matches ^sku-[a-z0-9 -]{3,32}$ ) max turns integer no cap on alternating offers. each turn costs a micro-escrow fee, so more turns is not free; the loop stops early once the spread closes. (1–5; defaults to 5 ) merchant did string no merchant to bargain with, when the sku is sold by more than one. omit to use the sku own merchant. a did you supply is never trusted as authority over price. (length 1–∞)"
  },
  {
    "route": "/docs/tool-reference#l4--settlement",
    "docTitle": "MCP tool reference",
    "headingText": "L4 · Settlement",
    "snippet": "Reserve stock, then build and sign the Google AP2 mandate chain -- Intent, Cart, Execution -- and settle it. Every mandate is Ed25519 over RFC 8785 canonical...",
    "searchText": "l4 · settlement mcp tool reference reserve stock, then build and sign the google ap2 mandate chain -- intent, cart, execution -- and settle it. every mandate is ed25519 over rfc 8785 canonical json."
  },
  {
    "route": "/docs/tool-reference#reserve_inventory_lock",
    "docTitle": "MCP tool reference",
    "headingText": "reserve_inventory_lock",
    "snippet": "Atomically reserves stock against a LIVE QUOTE and returns the four values create cart mandate needs: lock token, fencing token, expires at unix ms, and...",
    "searchText": "reserve_inventory_lock mcp tool reference atomically reserves stock against a live quote and returns the four values create cart mandate needs: lock token, fencing token, expires at unix ms, and signature. call get live sku quote first and pass its quote hash through unchanged -- a hash this mesh did not issue for this exact sku, quantity and buyer agent id is refused and no stock is reserved, so a refusal here costs you nothing and tells you what to fix. an out-of-stock refusal may also suggest an available substitute sku discovered via vector search; taking it requires requesting a fresh quote for that substitute sku. note the two clocks: your lock lasts lock ttl seconds, but the quote behind it dies 60 seconds after it was issued, and create cart mandate needs both alive. taking a lock longer than the quote does not extend the quote -- go straight from quote to lock to cart, and re-quote if you detour."
  },
  {
    "route": "/docs/tool-reference#reserve_inventory_lock-arguments",
    "docTitle": "MCP tool reference",
    "headingText": "reserve_inventory_lock arguments",
    "snippet": "Parameter Type Required Description --- --- --- --- buyer agent id string Yes The same DID you quoted with. The quote is bound to it, so a lock for a different...",
    "searchText": "reserve_inventory_lock arguments mcp tool reference parameter type required description --- --- --- --- buyer agent id string yes the same did you quoted with. the quote is bound to it, so a lock for a different agent is refused. lock ttl seconds integer yes how long the reservation is held. the 60s default already matches the quote's own lifetime; a longer lock outlives the quote it was taken against and cannot be carted. (10–120; defaults to 60 ) quantity integer yes must match the quantity the quote hash was issued for. quote again to lock a different number. (min 1) quote hash string yes from get live sku quote, unchanged. verified against the quotes this mesh issued before any stock moves. sku id string yes must match the sku the quote hash was issued for."
  },
  {
    "route": "/docs/tool-reference#establish_agent_delegation",
    "docTitle": "MCP tool reference",
    "headingText": "establish_agent_delegation",
    "snippet": "Pairs your agent with the mesh and issues a signed Intent Mandate delegating a bounded spending authority to your DID. The other three purchase tools take the...",
    "searchText": "establish_agent_delegation mcp tool reference pairs your agent with the mesh and issues a signed intent mandate delegating a bounded spending authority to your did. the other three purchase tools take the delegation id it returns -- but price the purchase before you call this. get live sku quote and verify shipping sla both answer without any delegation, and the cart charges exactly the shipping cost paise the sla returned, so offered unit price paise x quantity + total tax paise + shipping cost paise is the all-in total. set max budget paise from that figure, not from a guess you mean to correct afterwards -- see the ceiling rule below for why a correction upward will not be accepted. key custody has no default and you must state it. 'agent held': you keep your ed25519 private key, prove possession by signing the budget terms, and later sign the execution mandate yourself -- the mesh never holds buyer authority. 'mesh demo custodial': the mesh mints and holds the buyer key and returns the private key to you, because a custodial demo that hands you the key cannot be mistaken for a security boundary; in that mode the mesh can sign purchases with no human approval and the budget ceiling does not bind the mesh. authorized categories is enforced at settlement against the merchant-signed cart. in mesh demo custodial a delegation authorises a single purchase: the mesh discards the session buyer key once that purchase settles, so its lifetime is the purchase and not validity seconds. call this tool again for each further purchase -- reusing a settled delegation is refused, whatever budget it has left. know what that means for the ceiling you are given: the first max budget paise this session declares becomes the session ceiling and binds every later delegation too. a further establish agent delegation may lower that ceiling but can never raise it, because re-pairing is you reconnecting and not your buyer granting more money. so a provisional cap you intended to widen once you knew the price will hold you to the provisional figure and the purchase will be refused with nothing charged. across mcp sessions there is no ceiling at all and you are the one tracking the buyer's total. before you re-pair to retry, check whether the purchase you are redoing already settled. settling the same cart twice in one session is refused; settling it twice across sessions is not."
  },
  {
    "route": "/docs/tool-reference#establish_agent_delegation-arguments",
    "docTitle": "MCP tool reference",
    "headingText": "establish_agent_delegation arguments",
    "snippet": "Parameter Type Required Description --- --- --- --- key custody string Yes No default. State which party holds the buyer signing key. (one of agent held , mesh...",
    "searchText": "establish_agent_delegation arguments mcp tool reference parameter type required description --- --- --- --- key custody string yes no default. state which party holds the buyer signing key. (one of agent held , mesh demo custodial ) max budget paise integer yes total you may spend under this delegation, in paise (integer: 50000 is rs 500). the budget gate is deterministic -- a cart one paise over is refused. (min 1) single transaction limit paise integer yes clamped to max budget paise if larger. (min 1) authorized categories string[] no enforced at settlement against the category the merchant signed onto each cart line; a line outside this list aborts with ₹0 charged. use the merchant catalog's spellings (matched case-insensitively). empty means no restriction. (defaults to [] ) buyer agent id string no required for agent held; omitted otherwise. did:agent: plus 64 lowercase hex. (matches ^did:agent:[0-9a-f]{64}$ ) proof nonce string no random single-use string you signed over. replaying a nonce is refused. (length 1–∞) proof signature string no required for agent held. detached ed25519, 128 lowercase hex, over the rfc 8785 canonical json of {buyeragentid, maxbudgetpaise, nonce, singletransactionlimitpaise, timestamp}. (length 128–128) proof timestamp integer no unix seconds. accepted within -5s to +60s of mesh time. (min 1) validity seconds integer no how long this delegation stays usable, in seconds. every later call is refused once it lapses, so allow for negotiation turns and retries. (60–86400; defaults to 86400 )"
  },
  {
    "route": "/docs/tool-reference#create_cart_mandate",
    "docTitle": "MCP tool reference",
    "headingText": "create_cart_mandate",
    "snippet": "Produces a merchant-signed Cart Mandate from a live quote and a live inventory lock. The mesh re-derives every price from its own pricing and shipping engines...",
    "searchText": "create_cart_mandate mcp tool reference produces a merchant-signed cart mandate from a live quote and a live inventory lock. the mesh re-derives every price from its own pricing and shipping engines and compares the result against your quote hash, so the merchant signature attests only to numbers the merchant produced. call get live sku quote and reserve inventory lock first and pass their outputs through unchanged. the cart also fixes where the merchant is paid: the route payout account is resolved from the merchant identity signing this cart, so merchant account is not a destination you can choose. omit it."
  },
  {
    "route": "/docs/tool-reference#create_cart_mandate-arguments",
    "docTitle": "MCP tool reference",
    "headingText": "create_cart_mandate arguments",
    "snippet": "Parameter Type Required Description --- --- --- --- delegation id string Yes From establish agent delegation. Required on every later call. (length 1–∞)...",
    "searchText": "create_cart_mandate arguments mcp tool reference parameter type required description --- --- --- --- delegation id string yes from establish agent delegation. required on every later call. (length 1–∞) delivery pincode string yes destination pin code. an address no courier serves is refused here outright. (matches ^[1-9][0-9]{5}$ ) delivery state code string yes two-digit gst state code. decides intra- vs inter-state gst. (matches ^[0-9]{2}$ ) fencing token integer yes from reserve inventory lock. (min 1) lock expires at unix ms integer yes milliseconds, exactly as reserve inventory lock returned it. (min 1) lock signature string yes from reserve inventory lock, where this value is returned under the key 'signature' -- not 'lock signature'. pass it through unchanged. (length 1–∞) lock token string yes from reserve inventory lock. (length 1–∞) quantity integer yes units to buy. must equal the quantity you quoted, or the quote hash will not verify. (1–10000) quote hash string yes from get live sku quote. (length 1–∞) sku id string yes the sku you quoted and locked. it must match both. (matches ^sku-[a-z0-9 -]{3,32}$ ) merchant account string no do not send this. the razorpay route recipient for the merchant leg is resolved from the merchant identity that signs the cart, so it is not yours to choose. it is accepted only so that naming a different account is refused with a reason rather than silently ignored; the refusal names the account this merchant is actually paid at, and nothing is charged. (length 1–∞) package weight grams integer no billable weight in grams, the same one you checked the sla with. (min 1; defaults to 750 ) promo code string no optional. must be the same code you quoted with, if any. quote expiry timestamp integer no optional but recommended: pass quote expiry timestamp back exactly as get live sku quote returned it. supplying it lets the mesh tell an expired quote apart from a genuine parameter mismatch and refuse with a timeout you can act on. (min 1)"
  },
  {
    "route": "/docs/tool-reference#sign_execution_mandate",
    "docTitle": "MCP tool reference",
    "headingText": "sign_execution_mandate",
    "snippet": "Issues the Execution Mandate binding your Intent and Cart mandates together. In agent held mode it returns the exact RFC 8785 canonical JSON to sign and NO...",
    "searchText": "sign_execution_mandate mcp tool reference issues the execution mandate binding your intent and cart mandates together. in agent held mode it returns the exact rfc 8785 canonical json to sign and no signature: sign those bytes with your key and pass 128 lowercase hex to execute settlement. in mesh demo custodial mode the mesh signs with the session key it holds and returns a complete mandate. settle within 65 seconds -- the nonce ledger rejects a mandate signed outside that window. the settlement amount is taken from the stored cart and cannot be supplied by the caller."
  },
  {
    "route": "/docs/tool-reference#sign_execution_mandate-arguments",
    "docTitle": "MCP tool reference",
    "headingText": "sign_execution_mandate arguments",
    "snippet": "Parameter Type Required Description --- --- --- --- delegation id string Yes From establish agent delegation. (length 1–∞) cart mandate hash string No...",
    "searchText": "sign_execution_mandate arguments mcp tool reference parameter type required description --- --- --- --- delegation id string yes from establish agent delegation. (length 1–∞) cart mandate hash string no optional. selects a cart when the delegation holds more than one. (length 64–64)"
  },
  {
    "route": "/docs/tool-reference#execute_settlement",
    "docTitle": "MCP tool reference",
    "headingText": "execute_settlement",
    "snippet": "Submits the three-mandate bundle to the settlement saga and returns the capture, the Route split and the GSTR-1 invoice. A refusal -- replayed nonce, expired...",
    "searchText": "execute_settlement mcp tool reference submits the three-mandate bundle to the settlement saga and returns the capture, the route split and the gstr-1 invoice. a refusal -- replayed nonce, expired inventory lock, budget exceeded, bad signature, a merchant account that is not where the signing merchant is paid -- comes back as a tool result with iserror set and a machine-readable reason, not as a json-rpc error. a refusal means the protocol worked; read the reason rather than retrying blindly. the merchant leg of the split always pays the account registered to the merchantdid on the signed cart; no field on this call can move it."
  },
  {
    "route": "/docs/tool-reference#execute_settlement-arguments",
    "docTitle": "MCP tool reference",
    "headingText": "execute_settlement arguments",
    "snippet": "Parameter Type Required Description --- --- --- --- delegation id string Yes From establish agent delegation. (length 1–∞) execution id string Yes From sign...",
    "searchText": "execute_settlement arguments mcp tool reference parameter type required description --- --- --- --- delegation id string yes from establish agent delegation. (length 1–∞) execution id string yes from sign execution mandate. settlement is refused if the mandate it names has expired, so sign and settle without a long gap. (length 1–∞) agent signature string no required in agent held mode; rejected in mesh demo custodial mode. (length 128–128) merchant account string no do not send this. the route recipient for the merchant leg is resolved from the merchantdid on the signed cart mandate, never from this request, so it cannot redirect a payout. sending a value that differs from the resolved account is refused before anything is charged. (length 1–∞)"
  },
  {
    "route": "/docs/tool-reference#when-a-call-fails",
    "docTitle": "MCP tool reference",
    "headingText": "When a call fails",
    "snippet": "A failure comes back as a tool result with success: false , never as a missing response. The mesh distinguishes two kinds, and the distinction is on the...",
    "searchText": "when a call fails mcp tool reference a failure comes back as a tool result with success: false , never as a missing response. the mesh distinguishes two kinds, and the distinction is on the telemetry payload as failurekind : failurekind meaning what to do --- --- --- invalid request the arguments failed this tool's schema. the tables above list every constraint that can produce this fix the arguments and retry. nothing was refused refusal a well-formed call the mesh declined -- budget exceeded, mandate expired, stock gone, signature invalid read exceptioncode . retrying unchanged will fail identically a refusal carries a machine-readable exceptioncode alongside the message: both kinds are published to the telemetry stream and both are visible on the dashboard's live agent screen, counted separately: an agent misdialling an argument is not the protocol refusing it."
  },
  {
    "route": "/docs/telemetry",
    "docTitle": "Telemetry and event streaming",
    "headingText": "",
    "snippet": "Every service on the mesh publishes what it does to one event bus, and the dashboard is just a subscriber. This page is for anyone building a second subscriber...",
    "searchText": " telemetry and event streaming every service on the mesh publishes what it does to one event bus, and the dashboard is just a subscriber. this page is for anyone building a second subscriber -- an alerting hook, a ledger, a merchant's own order feed, a replica of the dashboard -- and covers how to subscribe, how to publish, what every event type carries, how the dashboard's metrics are derived, and what a merchant integration can and cannot join on. ---"
  },
  {
    "route": "/docs/telemetry#how-telemetry-flows",
    "docTitle": "Telemetry and event streaming",
    "headingText": "How telemetry flows",
    "snippet": "The RazorAgent Mesh v2.0 telemetry pipeline provides a high-throughput, low-latency asynchronous event streaming backbone for autonomous multi-agent commerce....",
    "searchText": "how telemetry flows telemetry and event streaming the razoragent mesh v2.0 telemetry pipeline provides a high-throughput, low-latency asynchronous event streaming backbone for autonomous multi-agent commerce. it captures the entire lifecycle of multi-agent interactions across all protocol layers—including model context protocol (mcp) json-rpc execution, rubinstein-ståhl bilateral bargaining concessions, sub-300ms vector semantic self-healing, ap2 cryptographic mandate signing, and 2-phase commit (2pc) multi-party settlements."
  },
  {
    "route": "/docs/telemetry#publish-and-subscribe",
    "docTitle": "Telemetry and event streaming",
    "headingText": "Publish and subscribe",
    "snippet": "The telemetry pipeline operates on an asynchronous Server-Sent Events (SSE) publish-subscribe model implemented via Python's asyncio primitives in...",
    "searchText": "publish and subscribe telemetry and event streaming the telemetry pipeline operates on an asynchronous server-sent events (sse) publish-subscribe model implemented via python's asyncio primitives in mandateengine/telemetryemitter.py ."
  },
  {
    "route": "/docs/telemetry#what-the-bus-guarantees",
    "docTitle": "Telemetry and event streaming",
    "headingText": "What the bus guarantees",
    "snippet": "1. Subscriber Queue Isolation & Capacity: Every connected listener receives a dedicated asyncio.Queue[str] configured with a capacity of 500 event frames (...",
    "searchText": "what the bus guarantees telemetry and event streaming 1. subscriber queue isolation & capacity: every connected listener receives a dedicated asyncio.queue[str] configured with a capacity of 500 event frames ( defaultqueuecapacity = 500 ). 2. non-blocking ingestion & backpressure handling: event publishing executes via put nowait() . if a client queue saturates because of slow network consumption, the server drops the stale queue rather than blocking the producer pipeline, preventing memory leakage and system degradation. 3. heartbeat keep-alive frame: when no event traffic occurs within 15 seconds ( heartbeatintervalseconds = 15 ), the server emits an sse comment heartbeat frame ( : heartbeat\\n\\n ) to preserve tcp socket persistence across load balancers, nat gateways, and reverse proxies. 4. resilient client auto-reconnection: client consumers implement exponential backoff reconnection logic: reconnection allows client consumers to recover automatically from transient socket resets without data loss. 5. thread-safe mutex lock: registration, unregistration, and broadcast dispatch across active subscriber queues are guarded by asyncio.lock() . ---"
  },
  {
    "route": "/docs/telemetry#streaming-api",
    "docTitle": "Telemetry and event streaming",
    "headingText": "Streaming API",
    "snippet": "",
    "searchText": "streaming api telemetry and event streaming "
  },
  {
    "route": "/docs/telemetry#subscribe-to-the-stream",
    "docTitle": "Telemetry and event streaming",
    "headingText": "Subscribe to the stream",
    "snippet": "Subscribes an HTTP client to the live telemetry event stream using standard HTTP/1.1 or HTTP/2 Server-Sent Events. Response headers SSE wire format Telemetry...",
    "searchText": "subscribe to the stream telemetry and event streaming subscribes an http client to the live telemetry event stream using standard http/1.1 or http/2 server-sent events. response headers sse wire format telemetry events are serialized to json with compact key-value separators ( , , : ) and prefixed with data: and terminated by \\n\\n : ---"
  },
  {
    "route": "/docs/telemetry#publish-an-event",
    "docTitle": "Telemetry and event streaming",
    "headingText": "Publish an event",
    "snippet": "Allows internal microservices, external agent gateways, or testing harnesses to ingest telemetry frames into the broadcast queue. Response ---",
    "searchText": "publish an event telemetry and event streaming allows internal microservices, external agent gateways, or testing harnesses to ingest telemetry frames into the broadcast queue. response ---"
  },
  {
    "route": "/docs/telemetry#health-check",
    "docTitle": "Telemetry and event streaming",
    "headingText": "Health check",
    "snippet": "Returns real-time service health status, active SSE subscriber counts, and subsystem connection readiness. Response ---",
    "searchText": "health check telemetry and event streaming returns real-time service health status, active sse subscriber counts, and subsystem connection readiness. response ---"
  },
  {
    "route": "/docs/telemetry#inspect-the-stream-from-a-terminal",
    "docTitle": "Telemetry and event streaming",
    "headingText": "Inspect the stream from a terminal",
    "snippet": "Developers and infrastructure engineers can consume and inspect the unbuffered live SSE feed directly from the command line using curl : Python client...",
    "searchText": "inspect the stream from a terminal telemetry and event streaming developers and infrastructure engineers can consume and inspect the unbuffered live sse feed directly from the command line using curl : python client consumption script: ---"
  },
  {
    "route": "/docs/telemetry#event-reference",
    "docTitle": "Telemetry and event streaming",
    "headingText": "Event reference",
    "snippet": "All telemetry events extend the base immutable envelope BaseTelemetryEvent and map directly to Pydantic models on the backend and TypeScript interfaces on the...",
    "searchText": "event reference telemetry and event streaming all telemetry events extend the base immutable envelope basetelemetryevent and map directly to pydantic models on the backend and typescript interfaces on the client. the table below is not written here -- it is read from the telemetryeventtype union and the badge map at build time, so it cannot fall behind the code the way a hand-counted list does. ---"
  },
  {
    "route": "/docs/telemetry#mcp_tool_call",
    "docTitle": "Telemetry and event streaming",
    "headingText": "MCP_TOOL_CALL",
    "snippet": "Emitted when an agent calls any tool on the MCP server. toolName carries whichever tool was called -- see the tool reference for the current set -- and...",
    "searchText": "mcp_tool_call telemetry and event streaming emitted when an agent calls any tool on the mcp server. toolname carries whichever tool was called -- see the tool reference for the current set -- and parameters carries the arguments exactly as the agent sent them, so a subscriber can reconstruct the call. typescript schema json payload ---"
  },
  {
    "route": "/docs/telemetry#mcp_tool_result",
    "docTitle": "Telemetry and event streaming",
    "headingText": "MCP_TOOL_RESULT",
    "snippet": "Emitted upon completion of an MCP tool invocation, reporting the execution status, output data, and exact latency in milliseconds ( durationMs ). TypeScript...",
    "searchText": "mcp_tool_result telemetry and event streaming emitted upon completion of an mcp tool invocation, reporting the execution status, output data, and exact latency in milliseconds ( durationms ). typescript schema json payload ---"
  },
  {
    "route": "/docs/telemetry#bid_turn_completed",
    "docTitle": "Telemetry and event streaming",
    "headingText": "BID_TURN_COMPLETED",
    "snippet": "Emitted after each Rubinstein-Ståhl bargaining turn, capturing the buyer's bid, the seller's ask, the spread in paise, and the anti-spam micro-escrow fee burn...",
    "searchText": "bid_turn_completed telemetry and event streaming emitted after each rubinstein-ståhl bargaining turn, capturing the buyer's bid, the seller's ask, the spread in paise, and the anti-spam micro-escrow fee burn (50 paise/turn). typescript schema json payload ---"
  },
  {
    "route": "/docs/telemetry#negotiation_converged",
    "docTitle": "Telemetry and event streaming",
    "headingText": "NEGOTIATION_CONVERGED",
    "snippet": "Emitted when the buyer bid and seller ask reach mathematical equilibrium , binding the agreed unit price and compiling the RFC 8785 Abstract Syntax Tree (AST)...",
    "searchText": "negotiation_converged telemetry and event streaming emitted when the buyer bid and seller ask reach mathematical equilibrium , binding the agreed unit price and compiling the rfc 8785 abstract syntax tree (ast) contract hash. typescript schema json payload ---"
  },
  {
    "route": "/docs/telemetry#mandate_signed",
    "docTitle": "Telemetry and event streaming",
    "headingText": "MANDATE_SIGNED",
    "snippet": "Emitted during each step of the 4-phase AP2 mandate chain lifecycle ( ), broadcasting non-repudiable Ed25519 signatures, RFC 8785 Canonical JSON previews, and...",
    "searchText": "mandate_signed telemetry and event streaming emitted during each step of the 4-phase ap2 mandate chain lifecycle ( ), broadcasting non-repudiable ed25519 signatures, rfc 8785 canonical json previews, and hash bindings. typescript schema json payload ---"
  },
  {
    "route": "/docs/telemetry#payment_captured",
    "docTitle": "Telemetry and event streaming",
    "headingText": "PAYMENT_CAPTURED",
    "snippet": "Emitted when 2-Phase Commit (2PC) settlement executes across Razorpay Route accounts, logging the four-way conserved split transfers and the statutory GSTR-1...",
    "searchText": "payment_captured telemetry and event streaming emitted when 2-phase commit (2pc) settlement executes across razorpay route accounts, logging the four-way conserved split transfers and the statutory gstr-1 sha-256 tax hash. typescript schema json payload ---"
  },
  {
    "route": "/docs/telemetry#oos_healed",
    "docTitle": "Telemetry and event streaming",
    "headingText": "OOS_HEALED",
    "snippet": "Emitted when the Vector Healer intercepts an out-of-stock SKU and executes an Approximate Nearest Neighbor (ANN) substitution in Qdrant within the sub-300ms...",
    "searchText": "oos_healed telemetry and event streaming emitted when the vector healer intercepts an out-of-stock sku and executes an approximate nearest neighbor (ann) substitution in qdrant within the sub-300ms sla. typescript schema json payload ---"
  },
  {
    "route": "/docs/telemetry#budget_blocked",
    "docTitle": "Telemetry and event streaming",
    "headingText": "BUDGET_BLOCKED",
    "snippet": "Emitted when an autonomous cart or execution mandate attempts to exceed the user's delegated spending cap, triggering a deterministic block with 0 external API...",
    "searchText": "budget_blocked telemetry and event streaming emitted when an autonomous cart or execution mandate attempts to exceed the user's delegated spending cap, triggering a deterministic block with 0 external api calls made. typescript schema json payload ---"
  },
  {
    "route": "/docs/telemetry#pow_challenge_solved",
    "docTitle": "Telemetry and event streaming",
    "headingText": "POW_CHALLENGE_SOLVED",
    "snippet": "Emitted upon verification of an ingress SHA-256 Proof-of-Work challenge, proving computational commitment to mitigate Sybil attacks and API flooding....",
    "searchText": "pow_challenge_solved telemetry and event streaming emitted upon verification of an ingress sha-256 proof-of-work challenge, proving computational commitment to mitigate sybil attacks and api flooding. typescript schema json payload ---"
  },
  {
    "route": "/docs/telemetry#inventory_locked",
    "docTitle": "Telemetry and event streaming",
    "headingText": "INVENTORY_LOCKED",
    "snippet": "Emitted when Redis acquires an atomic inventory reservation lock with a monotonically increasing fencing token and Time-To-Live (TTL). TypeScript schema JSON...",
    "searchText": "inventory_locked telemetry and event streaming emitted when redis acquires an atomic inventory reservation lock with a monotonically increasing fencing token and time-to-live (ttl). typescript schema json payload ---"
  },
  {
    "route": "/docs/telemetry#route_rollback_triggered",
    "docTitle": "Telemetry and event streaming",
    "headingText": "ROUTE_ROLLBACK_TRIGGERED",
    "snippet": "Emitted when a secondary transfer in a 2-Phase Commit settlement fails, triggering LIFO compensation reverse transfers to ensure transactional atomicity....",
    "searchText": "route_rollback_triggered telemetry and event streaming emitted when a secondary transfer in a 2-phase commit settlement fails, triggering lifo compensation reverse transfers to ensure transactional atomicity. typescript schema json payload ---"
  },
  {
    "route": "/docs/telemetry#heartbeat",
    "docTitle": "Telemetry and event streaming",
    "headingText": "HEARTBEAT",
    "snippet": "Emitted periodically every 15 seconds to maintain keep-alive persistence on the SSE streaming channel. TypeScript schema JSON payload ---",
    "searchText": "heartbeat telemetry and event streaming emitted periodically every 15 seconds to maintain keep-alive persistence on the sse streaming channel. typescript schema json payload ---"
  },
  {
    "route": "/docs/telemetry#merchant-side-subscribers",
    "docTitle": "Telemetry and event streaming",
    "headingText": "Merchant-side subscribers",
    "snippet": "The bus is not only the dashboard's feed. Today it is the only way a merchant finds out that one of its SKUs was sold : the mesh sends no order email, no SMS...",
    "searchText": "merchant-side subscribers telemetry and event streaming the bus is not only the dashboard's feed. today it is the only way a merchant finds out that one of its skus was sold : the mesh sends no order email, no sms and no merchant callback on capture. a merchant system integrates exactly as the dashboard does -- open get /api/v1/telemetry/stream and filter. this section is what that filter has to work with, including the two joins that are not where a reader expects them."
  },
  {
    "route": "/docs/telemetry#there-is-no-merchantdid-on-the-wire",
    "docTitle": "Telemetry and event streaming",
    "headingText": "There is no merchantDid on the wire",
    "snippet": "Worth stating first, because it is the field you would reach for. No emitter puts one on an event. Two joinable keys exist instead: Event Field Joins against...",
    "searchText": "there is no merchantdid on the wire telemetry and event streaming worth stating first, because it is the field you would reach for. no emitter puts one on an event. two joinable keys exist instead: event field joins against --- --- --- payment captured payload.transfers[].recipientaccountid the razorpayaccountid you gave at registration inventory locked payload.skuid the sku ids in your own catalog mandate signed carries signerkeydid , but that is the signer -- the buyer agent for an execution mandate, the mcp server for a cart mandate -- not a routing key for the merchant whose goods are being bought."
  },
  {
    "route": "/docs/telemetry#sessionid-does-not-join-across-the-settlement-boundary",
    "docTitle": "Telemetry and event streaming",
    "headingText": "sessionId does not join across the settlement boundary",
    "snippet": "The MCP server stamps its events with the buyer's session id. The mandate engine stamps PAYMENT CAPTURED with the payment id in that same field (...",
    "searchText": "sessionid does not join across the settlement boundary telemetry and event streaming the mcp server stamps its events with the buyer's session id. the mandate engine stamps payment captured with the payment id in that same field ( mandateengine/mandateapp.py , emitpaymentcapturedtelemetry : sessionid=payload.paymentid ), so a naive group-by sessionid splits one purchase in two and leaves the capture -- the event a merchant most wants -- orphaned in a session of its own. the join both sides already carry is the payment id: read payload.result.paymentid off the mcp tool result for execute settlement , then match it against the sessionid of the payment captured . the dashboard does exactly this in src/lib/liveagentsteps.ts ( mappaymentidstosessions ) rather than change the settlement wire contract to thread a session id through."
  },
  {
    "route": "/docs/telemetry#the-order-lifecycle-as-a-merchant-sees-it",
    "docTitle": "Telemetry and event streaming",
    "headingText": "The order lifecycle, as a merchant sees it",
    "snippet": "INVENTORY LOCKED (your stock is committed) → BID TURN COMPLETED / NEGOTIATION CONVERGED (only if you enabled bargaining) → MANDATE SIGNED (the buyer...",
    "searchText": "the order lifecycle, as a merchant sees it telemetry and event streaming inventory locked (your stock is committed) → bid turn completed / negotiation converged (only if you enabled bargaining) → mandate signed (the buyer authorised) → payment captured (money moved, and the payload carries the four transfer legs plus gstrinvoicehash ). route rollback triggered and budget blocked are the two branches where a lock you saw taken never becomes a sale -- treat them as the cue to release your own reservation."
  },
  {
    "route": "/docs/telemetry#a-minimal-merchant-listener",
    "docTitle": "Telemetry and event streaming",
    "headingText": "A minimal merchant listener",
    "snippet": "",
    "searchText": "a minimal merchant listener telemetry and event streaming "
  },
  {
    "route": "/docs/telemetry#what-is-not-built",
    "docTitle": "Telemetry and event streaming",
    "headingText": "What is not built",
    "snippet": "One gap and one half-built path, both worth knowing before you design around this page: 1. No order egress. Nothing emails, texts or calls a merchant back when...",
    "searchText": "what is not built telemetry and event streaming one gap and one half-built path, both worth knowing before you design around this page: 1. no order egress. nothing emails, texts or calls a merchant back when a sale settles. the mesh has exactly one outbound notification path and it serves a different purpose: signed price-drop alerts to a buyer callback url, registered at post /api/v1/alerts/price-drop on the x402 gateway and dispatched by x402gateway/src/alerts/pricedropalertmanager.py . a merchant order callback would follow that shape; it does not exist yet. 2. inbound razorpay webhooks are received, but nothing is reconciled against them. post /api/v1/webhooks/razorpay on the mandate engine verifies the hmac-sha256 signature with a timing-safe compare and rejects a delivery outside the 300-second freshness window ( webhookfreshnesswindowseconds ), de-duplicates on x-razorpay-event-id so a retry is processed once, and answers {\"status\": \"accepted\", \"reconciled\": false} . set razorpay webhook secret to enable it -- unset, the route answers 503 rather than accepting a payload it cannot verify. reconciled: false is the honest part. settlementresult is never persisted, so there is no order for a payment.failed or refund.created delivery to amend; the endpoint acknowledges and logs. reconciliation is blocked on order persistence, not on the receiver. ---"
  },
  {
    "route": "/docs/telemetry#metrics",
    "docTitle": "Telemetry and event streaming",
    "headingText": "Metrics",
    "snippet": "",
    "searchText": "metrics telemetry and event streaming "
  },
  {
    "route": "/docs/telemetry#formulas",
    "docTitle": "Telemetry and event streaming",
    "headingText": "Formulas",
    "snippet": "Total settled volume Aggregates the total settled transaction value in integer paise across all PAYMENT CAPTURED events: Settlement success rate Measures the...",
    "searchText": "formulas telemetry and event streaming total settled volume aggregates the total settled transaction value in integer paise across all payment captured events: settlement success rate measures the reliability of 2pc multi-party transfers: negotiation convergence rate quantifies the efficiency of bilateral rubinstein-ståhl bargaining turns reaching equilibrium within the maximum turn boundary ( ): average vector healing latency calculates the mean duration in milliseconds for the vector healer to resolve an out-of-stock exception via qdrant cosine similarity search: self-healing sla pass rate measures the percentage of vector substitutions that both complete under the 300ms deadline and satisfy 100% of negative constraints: micro-escrow fees collected calculates the total non-refundable anti-spam burn collected across all completed bargaining turns: route settlement conservation ensures zero-loss conservation of funds across multi-party split transfers: ---"
  },
  {
    "route": "/docs/telemetry#tests",
    "docTitle": "Telemetry and event streaming",
    "headingText": "Tests",
    "snippet": "Run the dedicated test suite verifying the telemetry emitter, SSE streaming async generator, subscriber queue management, and payload serialization:",
    "searchText": "tests telemetry and event streaming run the dedicated test suite verifying the telemetry emitter, sse streaming async generator, subscriber queue management, and payload serialization:"
  },
  {
    "route": "/docs/gstr1-invoice",
    "docTitle": "GSTR-1 invoicing",
    "headingText": "",
    "snippet": "Every settlement produces a tax invoice that has to stand up under Indian GST law. This page is for anyone who has to trust those numbers: it covers what Rule...",
    "searchText": " gstr-1 invoicing every settlement produces a tax invoice that has to stand up under indian gst law. this page is for anyone who has to trust those numbers: it covers what rule 46 requires, how the engine computes gst in integer paise without losing a paise to rounding, how a global discount is allocated across line items, and how each invoice is sealed so a later edit is detectable. ---"
  },
  {
    "route": "/docs/gstr1-invoice#what-the-law-requires",
    "docTitle": "GSTR-1 invoicing",
    "headingText": "What the law requires",
    "snippet": "Under the Indian Goods and Services Tax (GST) regime, autonomous multi-agent commerce must produce non-repudiable, statutory tax invoices that comply with all...",
    "searchText": "what the law requires gstr-1 invoicing under the indian goods and services tax (gst) regime, autonomous multi-agent commerce must produce non-repudiable, statutory tax invoices that comply with all applicable legal standards governing electronic invoicing and digital marketplace transactions."
  },
  {
    "route": "/docs/gstr1-invoice#legal-basis",
    "docTitle": "GSTR-1 invoicing",
    "headingText": "Legal basis",
    "snippet": "1. Section 31 of Central Goods and Services Tax (CGST) Act, 2017: Mandates that every registered taxable person supplying taxable goods or services must issue...",
    "searchText": "legal basis gstr-1 invoicing 1. section 31 of central goods and services tax (cgst) act, 2017: mandates that every registered taxable person supplying taxable goods or services must issue a tax invoice showing the description, quantity, value of goods, tax charged thereon, and other prescribed particulars. 2. rule 46 of cgst rules, 2017 (mandatory invoice particulars): requires sixteen essential particulars on every tax invoice, including: - name, address, and goods and services tax identification number ( gstin ) of the supplier. - a consecutive serial number not exceeding 16 characters containing alphabets, numerals, and special characters. - date of invoice issuance. - name, address, and gstin/unique identification number (uin) of the recipient. - harmonized system of nomenclature ( hsn ) code for goods or accounting code for services. - description of goods or services. - quantity of goods and unit of measurement. - total taxable value of supply of goods or services taking into account any discount or abatement. - rate of tax (central gst, state gst, integrated gst, or cess). - amount of tax charged in respect of taxable goods or services segregated by cgst, sgst, and igst. - place of supply along with the name of the state and its two-digit state code. - digital signature or electronic verification stamp of the supplier or authorized agent. 3. section 52 of cgst act, 2017 (tax collection at source / tcs): mandates that electronic commerce operators (eco) collect tcs at the rate of 1.00% (100 basis points) on the net value of taxable supplies made through the platform: - intra-state supplies: 0.50% cgst (50 bps) + 0.50% sgst (50 bps). - inter-state supplies: 1.00% igst (100 bps). ---"
  },
  {
    "route": "/docs/gstr1-invoice#the-tax-engine",
    "docTitle": "GSTR-1 invoicing",
    "headingText": "The tax engine",
    "snippet": "Financial calculations in RazorAgent Mesh are strictly isolated inside the Arithmetic Enclave ( mandateEngine/verification/arithmeticEnclave.py ). This enclave...",
    "searchText": "the tax engine gstr-1 invoicing financial calculations in razoragent mesh are strictly isolated inside the arithmetic enclave ( mandateengine/verification/arithmeticenclave.py ). this enclave guarantees mathematical precision and prevents floating-point drift, fractional penny discrepancies, and non-deterministic rounding errors across multi-party settlements."
  },
  {
    "route": "/docs/gstr1-invoice#integer-paise-arithmetic",
    "docTitle": "GSTR-1 invoicing",
    "headingText": "Integer paise arithmetic",
    "snippet": "- All financial values (prices, unit costs, discounts, shipping fees, tax components, and settlement splits) are represented strictly as integer paise ( ). -...",
    "searchText": "integer paise arithmetic gstr-1 invoicing - all financial values (prices, unit costs, discounts, shipping fees, tax components, and settlement splits) are represented strictly as integer paise ( ). - the use of floating-point types ( float , double ) in any financial calculation path is strictly forbidden and triggers an immediate arithmeticdriftexception ."
  },
  {
    "route": "/docs/gstr1-invoice#gst-calculation",
    "docTitle": "GSTR-1 invoicing",
    "headingText": "GST calculation",
    "snippet": "GST is computed independently per itemized line item using statutory floor division. CGST and SGST are two separate levies, each charged at exactly half the...",
    "searchText": "gst calculation gstr-1 invoicing gst is computed independently per itemized line item using statutory floor division. cgst and sgst are two separate levies, each charged at exactly half the combined rate, so both components are computed with the identical expression and are therefore always equal. the line total is defined as their sum, which makes penny conservation structural rather than something a rounding rule has to recover. place of supply intra-state supply (cgst + sgst) for supplies where the merchant and delivery location share the same two-digit gst state code: statutory equality guarantee: cgst and sgst are distinct levies each charged at half the combined rate, so they must be equal , not merely sum to the total. both are computed from the identical expression, which makes that equality hold by construction for every rate — including odd slabs such as 5%, where deriving one component as the remainder of the other would produce an illegal asymmetric split (2% / 3% instead of 2.5% / 2.5%). exact conservation guarantee: because is defined as , the identity holds with zero drift by definition. the single division by (equivalently, by when the rate is expressed in basis points) is deliberate: halving the rate first and then flooring twice would discard up to one paise per line item and put this engine one paise out of step with the typescript mcp quoter. inter-state supply (igst) for supplies across differing state jurisdictions: ---"
  },
  {
    "route": "/docs/gstr1-invoice#section-52-tcs-withholding",
    "docTitle": "GSTR-1 invoicing",
    "headingText": "Section 52 TCS withholding",
    "snippet": "Section 52 Tax Collection at Source (TCS) is computed on the net taxable base across the order: Intra-state TCS Inter-state TCS ---",
    "searchText": "section 52 tcs withholding gstr-1 invoicing section 52 tax collection at source (tcs) is computed on the net taxable base across the order: intra-state tcs inter-state tcs ---"
  },
  {
    "route": "/docs/gstr1-invoice#allocating-a-global-discount",
    "docTitle": "GSTR-1 invoicing",
    "headingText": "Allocating a global discount",
    "snippet": "When a global promotional discount ( ) is applied across line items with taxable values (where ), the discount is apportioned using the Hare-Niemeyer (Largest...",
    "searchText": "allocating a global discount gstr-1 invoicing when a global promotional discount ( ) is applied across line items with taxable values (where ), the discount is apportioned using the hare-niemeyer (largest remainder) algorithm to prevent fractional penny loss: 1. compute base floor allocations: 2. distribute residual paise: the remaining unallocated paise are assigned 1 paise at a time to the items with the largest fractional remainders . 3. conservation invariant: ---"
  },
  {
    "route": "/docs/gstr1-invoice#hsn-tax-slabs",
    "docTitle": "GSTR-1 invoicing",
    "headingText": "HSN tax slabs",
    "snippet": "The engine supports all 5 official GST tax rate tiers: Slab Rate (%) Statutory Category Representative HSN Codes --- --- --- --- Exempt 0% Unprocessed...",
    "searchText": "hsn tax slabs gstr-1 invoicing the engine supports all 5 official gst tax rate tiers: slab rate (%) statutory category representative hsn codes --- --- --- --- exempt 0% unprocessed agricultural products, essential food grains, raw milk 0401 (milk), 1001 (wheat) merit / essential 5% life-saving pharmaceuticals, packaged edible oils, economy textiles 3004 (medicaments), 1507 (soya oil) standard-1 12% processed foods, basic electronic components, diagnostic machinery 8418 (refrigerators), 9018 (medical instruments) standard-2 18% general electronics, commercial furniture, industrial capital goods 8504 (transformers), 9401 (furniture) demerit / luxury 28% luxury motor vehicles, premium consumer electronics, aerated drinks 8703 (automobiles), 2202 (beverages) bullion 3% gold 24k/22k coins & bars, silver ingots, jewelry articles 7113 (jewelry), 7108 (gold bullion) ---"
  },
  {
    "route": "/docs/gstr1-invoice#the-invoice-renderer",
    "docTitle": "GSTR-1 invoicing",
    "headingText": "The invoice renderer",
    "snippet": "The HTML generation subsystem ( mandateEngine/tax/gstrInvoiceHtmlRenderer.py ) converts structured GstrInvoicePayload models into self-contained, responsive,...",
    "searchText": "the invoice renderer gstr-1 invoicing the html generation subsystem ( mandateengine/tax/gstrinvoicehtmlrenderer.py ) converts structured gstrinvoicepayload models into self-contained, responsive, print-ready html documents."
  },
  {
    "route": "/docs/gstr1-invoice#document-layout",
    "docTitle": "GSTR-1 invoicing",
    "headingText": "Document layout",
    "snippet": "The rendered HTML document contains five distinct sections structured to satisfy Rule 46: 1. Header & Legal Classification Grid ( .header-grid ): - Title: TAX...",
    "searchText": "document layout gstr-1 invoicing the rendered html document contains five distinct sections structured to satisfy rule 46: 1. header & legal classification grid ( .header-grid ): - title: tax invoice - statutory citation: issued under section 31 of cgst act, 2017 & rule 46 of cgst rules - invoice metadata badge: invoice number, date, supply classification ( intra-state (cgst + sgst) or inter-state (igst) ). 2. entity details grid ( .details-grid ): - seller / supplier box: legal name, 15-character gstin, state name & 2-digit code. - recipient / place of supply box: recipient legal name, place of supply (pos) state & code, protocol identifier ( razoragent mesh v2.0 ). 3. itemized tax breakdown table ( .data-table ): - columns: , sku identifier , hsn , qty , unit price , taxable amt , rate , cgst , sgst , igst , line total . - table footer: sum of taxable subtotal, total cgst, total sgst, total igst, and total invoice value. 4. summary & tcs grid ( .bottom-grid ): - section 52 tcs card: net taxable base, statutory tcs rate (100 bps), and total tcs withheld. - financial summary card: taxable subtotal, total gst, shipping & handling, promotional discount, and grand total. 5. cryptographic audit verification stamp ( .audit-stamp ): - visual verified checkmark badge ( ✓ cryptographic verification & audit stamp ). - 64-character hexadecimal sha-256 digest rendered in a monospace code container. - non-repudiation certification stamp with timestamp. ---"
  },
  {
    "route": "/docs/gstr1-invoice#styling",
    "docTitle": "GSTR-1 invoicing",
    "headingText": "Styling",
    "snippet": "The renderer inlines its stylesheet from gstrInvoiceHtmlStyles.py , so an invoice is a single self-contained HTML file with no external requests -- which is...",
    "searchText": "styling gstr-1 invoicing the renderer inlines its stylesheet from gstrinvoicehtmlstyles.py , so an invoice is a single self-contained html file with no external requests -- which is what makes it safe to email or archive. the sheet lays the document out for screen and carries an @media print block that fixes it to a4 portrait and forces background colours to survive printing, so a printed copy and an archived copy are the same document. ---"
  },
  {
    "route": "/docs/gstr1-invoice#escaping-and-sanitisation",
    "docTitle": "GSTR-1 invoicing",
    "headingText": "Escaping and sanitisation",
    "snippet": "To prevent Cross-Site Scripting (XSS) or HTML tag breakout from untrusted merchant or product metadata, all dynamic strings (SKU identifiers, product titles,...",
    "searchText": "escaping and sanitisation gstr-1 invoicing to prevent cross-site scripting (xss) or html tag breakout from untrusted merchant or product metadata, all dynamic strings (sku identifiers, product titles, invoice numbers, merchant legal names, gstins, and timestamps) are sanitized using html.escape(value, quote=true) prior to string template interpolation. ---"
  },
  {
    "route": "/docs/gstr1-invoice#the-audit-hash",
    "docTitle": "GSTR-1 invoicing",
    "headingText": "The audit hash",
    "snippet": "For complete e-invoicing audit compliance and tamper-evidence, every generated tax invoice computes a Canonical JSON SHA-256 Digest following RFC 8785 (JSON...",
    "searchText": "the audit hash gstr-1 invoicing for complete e-invoicing audit compliance and tamper-evidence, every generated tax invoice computes a canonical json sha-256 digest following rfc 8785 (json canonicalization scheme - jcs) ."
  },
  {
    "route": "/docs/gstr1-invoice#canonical-payload",
    "docTitle": "GSTR-1 invoicing",
    "headingText": "Canonical payload",
    "snippet": "The invoice dictionary is normalized with deterministic key ordering and zero unquoted whitespace:",
    "searchText": "canonical payload gstr-1 invoicing the invoice dictionary is normalized with deterministic key ordering and zero unquoted whitespace:"
  },
  {
    "route": "/docs/gstr1-invoice#computing-the-hash",
    "docTitle": "GSTR-1 invoicing",
    "headingText": "Computing the hash",
    "snippet": "The canonicalized UTF-8 bytes are passed through SHA-256: This yields a 64-character hexadecimal digest (e.g.,...",
    "searchText": "computing the hash gstr-1 invoicing the canonicalized utf-8 bytes are passed through sha-256: this yields a 64-character hexadecimal digest (e.g., a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90 ), which is stamped into the invoice document and recorded on the ledger for statutory tax reconciliation. ---"
  },
  {
    "route": "/docs/gstr1-invoice#gst-state-codes",
    "docTitle": "GSTR-1 invoicing",
    "headingText": "GST state codes",
    "snippet": "The tax engine includes an internal registry mapping all 37 official two-digit Indian GST state and Union Territory codes: Code State / Union Territory Code...",
    "searchText": "gst state codes gstr-1 invoicing the tax engine includes an internal registry mapping all 37 official two-digit indian gst state and union territory codes: code state / union territory code state / union territory --- --- --- --- 01 jammu & kashmir 20 jharkhand 02 himachal pradesh 21 odisha 03 punjab 22 chhattisgarh 04 chandigarh 23 madhya pradesh 05 uttarakhand 24 gujarat 06 haryana 26 dadra & nagar haveli and daman & diu 07 delhi 27 maharashtra 08 rajasthan 29 karnataka 09 uttar pradesh 30 goa 10 bihar 31 lakshadweep 11 sikkim 32 kerala 12 arunachal pradesh 33 tamil nadu 13 nagaland 34 puducherry 14 manipur 35 andaman & nicobar islands 15 mizoram 36 telangana 16 tripura 37 andhra pradesh 17 meghalaya 38 ladakh 18 assam 97 other territory 19 west bengal ---"
  },
  {
    "route": "/docs/gstr1-invoice#tests",
    "docTitle": "GSTR-1 invoicing",
    "headingText": "Tests",
    "snippet": "Verify the GSTR-1 tax calculation engine and HTML rendering pipeline using pytest:",
    "searchText": "tests gstr-1 invoicing verify the gstr-1 tax calculation engine and html rendering pipeline using pytest:"
  }
];
