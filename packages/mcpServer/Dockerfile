# ---- builder: full dependency tree, compiles src/ to dist/ ----
FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json tsconfig.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

# ---- runner: compiled output plus the four production dependencies ----
FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY package.json package-lock.json ./
# ioredis, tweetnacl, uuid, zod only -- the TypeScript toolchain (typescript, tsx and its
# esbuild binaries, @types/*) is 33 of the 45 lockfile packages and is build-time only.
RUN npm ci --omit=dev --no-audit --no-fund
COPY --from=builder --chown=node:node /app/dist ./dist

USER node
EXPOSE 4001
CMD ["node", "dist/mcpServerMain.js"]
