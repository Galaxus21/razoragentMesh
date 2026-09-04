// GENERATED FILE -- DO NOT EDIT BY HAND.
//
// Produced by scripts/generateDocsManifest.ts from the frontmatter of docs/**/*.mdx.
// Regenerate with: npm run docs:manifest
// A test (test/docsPipeline.test.ts) fails if this file no longer matches the docs directory,
// so a stale manifest cannot ship silently.

import type { DocNavEntry } from "@/types/docsTypes";

export const docsManifest: readonly DocNavEntry[] = [
  {
    "slug": "setup",
    "route": "/docs/setup",
    "navLabel": "System Setup",
    "navDescription": "Prerequisites, .env and Docker",
    "title": "Setup and installation",
    "description": "Prerequisites, environment configuration, starting the stack with Docker Compose, verifying each service, and running packages without Docker.",
    "order": 1,
    "icon": "Server",
    "section": "Get started"
  },
  {
    "slug": "agent-quickstart",
    "route": "/docs/agent-quickstart",
    "navLabel": "Agent Quickstart",
    "navDescription": "Drive the mesh from your own agent",
    "title": "Agent quickstart",
    "description": "Connect an external agent -- Claude Desktop, Claude Code, Cursor -- to the mesh over MCP, publish a product, and drive a signed purchase while the telemetry stream renders it live.",
    "order": 2,
    "icon": "Plug",
    "section": "Get started"
  },
  {
    "slug": "onboarding",
    "route": "/docs/onboarding",
    "navLabel": "Developer Onboarding",
    "navDescription": "End-to-end integration guide",
    "title": "Developer onboarding",
    "description": "The path from a running stack to a settled purchase: the protocol's shape, keys and identities, what a merchant publishes, what a buyer agent calls, and how a settlement is verified.",
    "order": 3,
    "icon": "Rocket",
    "section": "Guides"
  },
  {
    "slug": "buyer-sdk",
    "route": "/docs/buyer-sdk",
    "navLabel": "Buyer SDK",
    "navDescription": "TypeScript and Python client guide",
    "title": "Buyer SDK",
    "description": "Build a buyer agent with the TypeScript or Python SDK: client setup, quotes and discounts, negotiation, inventory locks, signing and verifying the AP2 mandate chain, and settlement.",
    "order": 4,
    "icon": "Bot",
    "section": "Guides"
  },
  {
    "slug": "merchant-guide",
    "route": "/docs/merchant-guide",
    "navLabel": "Merchant Guide",
    "navDescription": "Catalog ingestion and pricing",
    "title": "Merchant guide",
    "description": "Register a merchant identity, publish a catalog, configure volume discount tiers, price bullion from the live spot oracle, get the HSN code and GST rate right, and subscribe to the bus that tells you a sale happened.",
    "order": 5,
    "icon": "Store",
    "section": "Guides"
  },
  {
    "slug": "tool-reference",
    "route": "/docs/tool-reference",
    "navLabel": "Tool Reference",
    "navDescription": "Every tool and argument",
    "title": "MCP tool reference",
    "description": "Every tool an autonomous agent can call on the mesh, with its exact arguments, constraints and defaults, generated from the JSON Schema the server returns from tools/list.",
    "order": 6,
    "icon": "Terminal",
    "section": "Reference"
  },
  {
    "slug": "telemetry",
    "route": "/docs/telemetry",
    "navLabel": "Telemetry & SSE",
    "navDescription": "Observability event streams",
    "title": "Telemetry and event streaming",
    "description": "The SSE bus every service publishes to: how to subscribe, how to publish, the schema of all twelve event types, the metrics the dashboard derives from them, and how a merchant builds an order feed on the same stream.",
    "order": 7,
    "icon": "Activity",
    "section": "Reference"
  },
  {
    "slug": "gstr1-invoice",
    "route": "/docs/gstr1-invoice",
    "navLabel": "GSTR-1 Invoicing",
    "navDescription": "Statutory tax specification",
    "title": "GSTR-1 invoicing",
    "description": "How the mesh computes Indian GST in integer paise, allocates discounts without losing a paise, withholds TCS under Section 52, and seals each invoice with a canonical audit hash.",
    "order": 8,
    "icon": "Receipt",
    "section": "Reference"
  }
];
