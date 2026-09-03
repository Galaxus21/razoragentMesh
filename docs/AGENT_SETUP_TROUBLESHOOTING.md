# Troubleshooting the external-agent setup

Every symptom below was observed on a real run of this repo, or is a failure the setup makes
easy to hit. Each entry gives the exact message, the cause, and the fix.

Entries marked **[fixed]** are already corrected in the code; they are kept because the symptom
can reappear from a stale image, a stale `.next` directory, or a partial rebuild.

---

## Connecting an agent to the mesh

### `EADDRINUSE: address already in use :::4001` **[fixed]**

Launching the server over stdio also tried to bind the HTTP port, which Docker already holds.
The stdio session died before the first tool call.

Set the transport explicitly. An MCP client that spawns its own copy must use stdio only:

```bash
MCP_TRANSPORT=stdio node dist/mcpServerMain.js
```

`MCP_TRANSPORT` accepts `stdio`, `http`, or `both` (default `both`). The Docker service sets
`http` because the container has no stdin attached.

### The client connects, then immediately disconnects **[fixed]**

The server answered `notifications/initialized` with `-32601 Method not found`. That message is a
JSON-RPC *notification* — it carries no `id` and must receive no reply at all. A strict client
treats the reply as a protocol violation and aborts before any tool call.

If you see this again, the server is out of date; rebuild it.

### `tools/list` returns three tools, not four

`search_catalog` is missing, so the agent can only quote SKU ids it was handed and cannot
discover anything. The image predates the discovery tool. Rebuild:

```bash
docker compose up -d --build mcp-server
```

### `Catalog search is unavailable at http://localhost:4002/api/v1/catalog/search`

`MERCHANT_API_URL` is unset in the mcp-server environment, so it fell back to `localhost`, which
inside a container is the container itself. The compose file sets
`MERCHANT_API_URL=http://merchant-api:4002`; a hand-run server outside Docker needs it too.

Ranking lives in merchantApi because that service owns the embedding model and the Qdrant
client. The MCP server is TypeScript and has no embedder.

---

## Search returns odd or meaningless results

### `embedding_mode` comes back as `hash`

The results are **not** semantically ranked. The server fell back to a character-hash
pseudo-vector, in which the ordering carries no meaning and the top hit is not a reasoned
choice. Every `search_catalog` response reports this field for exactly this reason — a silent
fallback would look like working semantic search that simply returns strange answers.

Common causes:

- **`Model all-MiniLM-L6-v2 is not supported in TextEmbedding`** **[fixed]** — fastembed
  requires the fully qualified name `sentence-transformers/all-MiniLM-L6-v2`. The short name
  raises at load time and the code fell back to hashing.
- The model has not finished downloading. The first call after a cold start pays for the
  download; later calls are served from the local cache.

### Search returns nothing, but the item is in the dashboard

The listing reached Redis but never reached the vector index. Two causes have produced this:

- **`... is not a valid point ID, valid values are either an unsigned integer or a UUID`**
  **[fixed]** — Qdrant rejected SKU strings used directly as point ids, and the rejection was
  logged at INFO, below uvicorn's default level, so an upsert that rejected every point looked
  exactly like one that worked. Point ids are now `uuid5(NAMESPACE_URL, skuId)` and the failure
  logs at WARNING. The SKU stays recoverable from the point payload.
- **Collection name mismatch** **[fixed]** — the service wrote to `merchant_products` while the
  seeder populated `razoragent_catalog`, so searches read an empty collection.

Confirm the index actually grew:

```bash
curl http://localhost:6333/collections/razoragent_catalog
```

### `UserWarning: Qdrant client version 1.19.0 is incompatible with server version 1.13.0`

Cosmetic in this repo — the calls used here are stable across both versions. It appears in test
output. Pin the client if you want it silent.

---

## Dashboard

### Publishing from Merchant Studio returns 404 **[fixed]**

The form posted to a merchantApi path relative to the dashboard's own origin, so the request
never left port 3000. Publishing now goes through the server-side proxy at `/api/mesh/catalog`.

Note the shape of the original bug: the failure was reported to the user as
`"Validated payload synthesized and ready for deployment"` — a success message on a failed
request. A test existed, but it reimplemented the publish logic locally instead of importing it,
so it passed while the feature was broken.

### `500` from the dev server, `Cannot find module './873.js'`

A production `npm run build` overwrote the `.next` directory the dev server was serving from.
Clear it and restart:

```bash
rm -rf packages/telemetryDashboard/.next
```

### Panels stay dark while the agent is clearly working

The MCP server publishes tool activity to the mandate engine, which owns the SSE bus. If
`MANDATE_ENGINE_URL` is unset, tool calls still succeed but nothing renders until settlement.

Telemetry is fire-and-forget by design: a dead bus must never fail a tool call. That is what
makes this failure quiet, so check the variable rather than the tool.

Verify the bus directly:

```bash
curl -N http://localhost:8000/api/v1/telemetry/stream
```

Each MCP call emits `MCP_TOOL_CALL` and `MCP_TOOL_RESULT` carrying the transport's session id,
which is what groups one agent's run in the UI.

---

## Environment

### `docker compose` fails with a daemon connection error

Docker Desktop is not running. Every service here is containerised except an MCP server you
launch yourself over stdio.

### Ports already in use

The mesh binds `3000` (dashboard), `4001` (MCP), `4002` (merchant API), `4003` (x402 gateway),
`6333`/`6334` (Qdrant), `6379` (Redis), and `8000` (mandate engine).

### The catalog is empty on a fresh start

`catalog-seeder` is a one-shot job that loads `tests/fixtures/catalogFixtures.json` and exits.
`Exited (0)` is success, not a crash. Services that need seeded data wait on
`service_completed_successfully`.

The fixtures are industrial parts. Anything you publish from the dashboard is yours and is not
in the fixtures, so it will not survive `docker compose down -v`.

---

## Writing your own MCP client

### `SyntaxError: Unexpected token ':', ": keepaliv"... is not valid JSON`

The Streamable HTTP transport replies as Server-Sent Events, and a slow call — the first search
after a cold start, while the embedding model loads — emits keepalive **comment** lines before
the data event:

```
: keepalive

data: {"jsonrpc":"2.0","id":3,"result":{...}}
```

A parser that inspects only the first line mistakes the comment for the body. Scan for the line
beginning `data:` rather than assuming it comes first. Official MCP SDK clients handle this;
only hand-rolled probes hit it.

### The handshake must be completed before any tool call

`initialize`, then the `notifications/initialized` notification, then `tools/call`. Carry the
`Mcp-Session-Id` header returned by `initialize` on every later request. The notification has no
`id` and correctly returns `202` with an empty body — that is success, not a dropped request.
