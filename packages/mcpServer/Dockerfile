# Build context is the REPOSITORY ROOT (see docker-compose.yml), not this package directory.
# The mandate tools import the real buyer SDK (`@razorpay/agent-buyer-sdk`, declared as
# `file:../buyerSdkTs`) for AgentKeyManager, createSignedCartMandate, computeMandateHash and
# extractPublicKeyFromDid, so the build needs both packages in scope. merchant-api,
# x402-gateway and telemetry-dashboard already build from the root context for the same reason.
#
# This image previously built from ./packages/mcpServer. That worked only while the server had
# no cross-package dependency: once the mandate tools started importing the SDK, `npm ci` inside
# the image could not resolve `file:../buyerSdkTs` -- the sibling package was outside the
# context -- and `npm run build` failed with exit 2 while a host-side `npm run build` still
# passed, because on the host ../buyerSdkTs really is there.

# ---- sdk: compile the TypeScript buyer SDK the mandate tools link against ----
FROM node:22-alpine AS sdk
WORKDIR /sdk
COPY packages/buyerSdkTs/package.json packages/buyerSdkTs/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY packages/buyerSdkTs/tsconfig.json ./
COPY packages/buyerSdkTs/src ./src
# `main` is dist/index.js, so the package is unusable until tsc runs. The second install swaps
# the toolchain for production dependencies only: npm SYMLINKS a file: dependency rather than
# copying it, and does NOT hoist the linked package's own deps into the consumer, so tweetnacl
# and uuid must stay resolvable from inside this directory.
RUN npm run build && npm ci --omit=dev --no-audit --no-fund

# ---- builder: full dependency tree, compiles src/ to dist/ ----
FROM node:22-alpine AS builder
WORKDIR /app/packages/mcpServer
# The file: dependency resolves relative to this package, so the SDK must sit at ../buyerSdkTs.
COPY --from=sdk /sdk /app/packages/buyerSdkTs
COPY packages/mcpServer/package.json packages/mcpServer/package-lock.json packages/mcpServer/tsconfig.json ./
RUN npm ci --no-audit --no-fund
COPY packages/mcpServer ./
RUN npm run build

# ---- runner: compiled output plus production dependencies ----
FROM node:22-alpine AS runner
WORKDIR /app/packages/mcpServer
ENV NODE_ENV=production
COPY --from=sdk /sdk /app/packages/buyerSdkTs
COPY packages/mcpServer/package.json packages/mcpServer/package-lock.json ./
# The TypeScript toolchain (typescript, tsx and its esbuild binaries, @types/*) is build-time
# only and is dropped here; @razorpay/agent-buyer-sdk is NOT -- the mandate tools call into it
# at runtime, so it stays and is symlinked to the sibling copied above.
RUN npm ci --omit=dev --no-audit --no-fund
COPY --from=builder --chown=node:node /app/packages/mcpServer/dist ./dist

USER node
EXPOSE 4001
CMD ["node", "dist/mcpServerMain.js"]
