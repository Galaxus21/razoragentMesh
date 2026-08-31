# Build context is the REPOSITORY ROOT (see docker-compose.yml), not this package directory.
# The dashboard's protocol driver imports the real buyer SDK (`@razorpay/agent-buyer-sdk`,
# declared as `file:../buyerSdkTs`), so the build needs both packages in scope. merchant-api
# and x402-gateway already build from the root context for the same reason.

# ---- sdk: compile the TypeScript buyer SDK the dashboard links against ----
FROM node:22-alpine AS sdk
WORKDIR /sdk
COPY packages/buyerSdkTs/package.json packages/buyerSdkTs/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY packages/buyerSdkTs/tsconfig.json ./
COPY packages/buyerSdkTs/src ./src
# `main` is dist/index.js, so the package is unusable until tsc runs. Afterwards the toolchain
# devDependencies are swapped for production ones only: npm SYMLINKS a file: dependency rather
# than copying it, and does NOT hoist the linked package's own deps into the consumer, so
# tweetnacl and uuid must remain resolvable from inside this directory or the Next build fails
# with "Module not found: Can't resolve 'tweetnacl'".
RUN npm run build && npm ci --omit=dev --no-audit --no-fund

# ---- deps: production + build dependencies, installed from the lockfile ----
FROM node:22-alpine AS deps
WORKDIR /app/packages/telemetryDashboard
# The file: dependency resolves relative to this package, so the SDK must sit at ../buyerSdkTs.
COPY --from=sdk /sdk /app/packages/buyerSdkTs
COPY packages/telemetryDashboard/package.json packages/telemetryDashboard/package-lock.json ./
RUN npm ci --no-audit --no-fund

# ---- builder: next build, which emits .next/standalone ----
FROM node:22-alpine AS builder
WORKDIR /app/packages/telemetryDashboard
COPY --from=sdk /sdk /app/packages/buyerSdkTs
COPY --from=deps /app/packages/telemetryDashboard/node_modules ./node_modules
# docs/ must be present here: the /docs/* pages prerender by reading it from disk
# (src/lib/docsLoader.ts), so excluding it from the build context breaks the build output.
COPY packages/telemetryDashboard ./
# NEXT_PUBLIC_* vars are inlined into the client bundle by `next build` -- they cannot be
# supplied at container runtime, so this must be a build ARG, not a runner-stage ENV.
# Passed via docker-compose.yml's `build.args`; defaults to the mandate-engine's published
# host port for a plain `docker build` with no compose (matches src/constants/dashboardConstants.ts).
ARG NEXT_PUBLIC_TELEMETRY_SSE_URL=http://localhost:8000/api/v1/telemetry/stream
ENV NEXT_PUBLIC_TELEMETRY_SSE_URL=$NEXT_PUBLIC_TELEMETRY_SSE_URL
RUN npm run build

# ---- runner: standalone server only, no devDependencies, no .next/cache ----
FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
# server.js binds localhost by default, which is unreachable from outside the container.
ENV HOSTNAME=0.0.0.0
ENV PORT=3000

# .next/standalone mirrors the source tree layout, so the server entrypoint lands under
# packages/telemetryDashboard/. Everything below is copied relative to that.
COPY --from=builder --chown=node:node /app/packages/telemetryDashboard/.next/standalone ./
# Static assets are deliberately omitted from standalone and must be copied separately,
# otherwise the page renders but every /_next/static chunk 404s.
COPY --from=builder --chown=node:node /app/packages/telemetryDashboard/.next/static ./packages/telemetryDashboard/.next/static
COPY --from=builder --chown=node:node /app/packages/telemetryDashboard/public ./packages/telemetryDashboard/public
# docsLoader.ts resolves this path at runtime, so the file tracer cannot see it.
COPY --from=builder --chown=node:node /app/packages/telemetryDashboard/docs ./packages/telemetryDashboard/docs

USER node
EXPOSE 3000
CMD ["node", "packages/telemetryDashboard/server.js"]
