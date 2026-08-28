# RazorAgent Mesh v2.0 — Technical Documentation Hub

Welcome to the **RazorAgent Mesh v2.0** technical documentation directory. This hub contains comprehensive architectural, developer onboarding, telemetry observability, and regulatory tax compliance specifications for the autonomous agentic commerce platform.

---

## Active Documentation Index

| Document | Primary Audience | Core Scope & Coverage |
|---|---|---|
| 📖 [**Developer Onboarding Guide**](./DEVELOPER_ONBOARDING_GUIDE.md) | Merchant Developers, AI Buyer Architects, Integrators | Complete protocol topology, Ed25519 DID minting, merchant registration & catalog ingestion (REST, CSV, Shopify, ERP), dynamic bullion spot pricing, statutory HSN chapters, AP2 budget gates, MCP JSON-RPC tools, and 2PC settlement sagas in TypeScript and Python. |
| 📡 [**Telemetry & Observability Guide**](./TELEMETRY_OBSERVABILITY_GUIDE.md) | Platform Engineers, DevOps, Reliability Teams | Real-time Server-Sent Events (SSE) streaming pipeline, 12 event schema models, pub/sub architecture, KPI metrics computation formulas, terminal health probes, and live audit telemetry feeds. |
| 📑 [**GSTR-1 Tax & Invoicing Specification**](./GSTR1_INVOICE_SPECIFICATION.md) | CFOs, Tax Auditors, Financial Engineers | Indian GST Rule 46 compliance, statutory intra-state (CGST + SGST) vs inter-state (IGST) math, Section 52 TCS withholding, integer paise floor division (INV-01 / INV-02), and SHA-256 cryptographic audit digests. |

---

## Protocol Overview

RazorAgent Mesh v2.0 is built on 5 deterministic layers:

1. **Layer 0 (Ingress Shield)**: Anti-spam and Sybil resistance via SHA-256 dynamic Proof-of-Work (PoW) and distributed anti-replay nonce tracking.
2. **Layer 1 (Deterministic Discovery)**: Anthropic Model Context Protocol (MCP) JSON-RPC 2.0 tools with 4-tier automated discount stacking and constant-time HMAC-SHA256 quotation signing.
3. **Layer 2 (Dynamic Negotiation)**: HTTP 402-INR micro-metered bilateral bargaining over Rubinstein-Ståhl state machines with monotonic concession enforcement.
4. **Layer 3 (Vector Healing)**: Sub-300ms out-of-stock substitution and semantic healing via Qdrant dense vector search.
5. **Layer 4 (AP2 Settlement Enclave)**: Ed25519 triple-mandate chain ($M_I \to M_C \to M_E \to M_A$), Two-Phase Commit (2PC) saga coordination, 3-way Razorpay Route split payouts, automated LIFO compensation rollback, and GSTR-1 e-invoicing.

---

## Quick Reference Links

- **Root Project Overview**: [`../PROJECT.md`](../PROJECT.md)
- **Comprehensive Architecture Guide**: [`../GUIDE.md`](../GUIDE.md)
- **Protocol Specification**: [`../../RAZORAGENT_MESH_V2_SPECIFICATION.md`](../../RAZORAGENT_MESH_V2_SPECIFICATION.md)
- **Master Knowledge Graph**: [`../../.agents/rules/project-knowledge-base.md`](../../.agents/rules/project-knowledge-base.md)
