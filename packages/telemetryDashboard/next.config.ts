import path from "node:path";
import { fileURLToPath } from "node:url";
import type { NextConfig } from "next";

const packageDir = path.dirname(fileURLToPath(import.meta.url));

const nextConfig: NextConfig = {
  // Emits .next/standalone: a self-contained server bundling only the production
  // dependencies Next's file tracer proves are reachable. Keeps devDependencies
  // (TypeScript, Tailwind, tsx, @types/*) and .next/cache out of the runtime image.
  output: "standalone",
  // `@razorpay/agent-buyer-sdk` is a file: dependency resolving to ../buyerSdkTs, which sits
  // OUTSIDE this package. Without an explicit tracing root Next infers one from this
  // package's lockfile and silently omits the SDK from the standalone bundle, so the
  // protocol driver would throw MODULE_NOT_FOUND at runtime but build cleanly.
  outputFileTracingRoot: path.join(packageDir, "..", ".."),
  reactStrictMode: true,
  poweredByHeader: false,
};

export default nextConfig;
