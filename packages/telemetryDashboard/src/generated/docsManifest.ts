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
    "navDescription": "Environment & Architecture Setup",
    "title": "System Setup & Environment Architecture Guide",
    "description": "Guides platform operators and engineers through prerequisites, environment configuration, Docker Compose deployment, health verification, and local development.",
    "order": 1,
    "icon": "Server"
  },
  {
    "slug": "agent-quickstart",
    "route": "/docs/agent-quickstart",
    "navLabel": "Agent Quickstart",
    "navDescription": "Drive the Mesh From Your Own Agent",
    "title": "Connect Your Own Agent — MCP Quickstart",
    "description": "Connects an external AI agent (Claude Desktop, Claude Code, Cursor) to the mesh over MCP, publishes inventory from the dashboard, and drives a real signed purchase while the telemetry stream renders it live.",
    "order": 2,
    "icon": "Plug"
  },
  {
    "slug": "onboarding",
    "route": "/docs/onboarding",
    "navLabel": "Developer Onboarding",
    "navDescription": "End-to-End Integration Guide",
    "title": "RazorAgent Mesh v2.0 — Developer Onboarding Guide",
    "description": "Provides an integration guide for merchants and buyer agents covering key management, catalog ingestion, AP2 mandates, 2PC settlement, and code examples.",
    "order": 3,
    "icon": "Rocket"
  },
  {
    "slug": "buyer-sdk",
    "route": "/docs/buyer-sdk",
    "navLabel": "Buyer SDK",
    "navDescription": "TypeScript & Python SDK Guide",
    "title": "AI Buyer Agent SDK & AP2 Protocol Guide",
    "description": "Explains how to use the buyer agent SDK for mandate signing, live SKU quoting, inventory locking, and 2PC settlement execution.",
    "order": 4,
    "icon": "Bot"
  },
  {
    "slug": "merchant-guide",
    "route": "/docs/merchant-guide",
    "navLabel": "Merchant Guide",
    "navDescription": "Catalog Ingestion & Pricing",
    "title": "Merchant Onboarding & Universal SKU Studio Guide",
    "description": "Guides merchants on registering DIDs, ingesting catalogs, configuring volume discounts, setting bullion spot formulas, and applying statutory HSN tax rules.",
    "order": 5,
    "icon": "Store"
  },
  {
    "slug": "telemetry",
    "route": "/docs/telemetry",
    "navLabel": "Telemetry & SSE",
    "navDescription": "Observability Event Streams",
    "title": "RazorAgent Mesh v2.0 — Real-Time Telemetry & Event Streaming Specification",
    "description": "Defines the real-time SSE telemetry architecture, event streaming endpoints, canonical event schemas, metric algorithms, and testing procedures.",
    "order": 6,
    "icon": "Activity"
  },
  {
    "slug": "gstr1-invoice",
    "route": "/docs/gstr1-invoice",
    "navLabel": "GSTR-1 Invoicing",
    "navDescription": "Statutory Tax Specification",
    "title": "Statutory GSTR-1 Tax Invoice Specification & Deterministic Integer Tax Engine",
    "description": "Defines the legal framework, integer paise GST calculations, HTML invoice rendering, cryptographic audit digests, and state codes for GSTR-1 compliance.",
    "order": 7,
    "icon": "Receipt"
  }
];
