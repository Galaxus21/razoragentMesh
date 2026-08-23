import type { NextConfig } from "next";

const telemetrySseEndpointUrl = process.env.NEXT_PUBLIC_TELEMETRY_SSE_URL ?? "http://localhost:8000/api/v1/telemetry/stream";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  env: {
    telemetrySseEndpointUrl,
  },
};

export default nextConfig;
