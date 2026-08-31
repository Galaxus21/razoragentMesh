// The mesh's HTTP services and where their liveness probes live.
//
// Health paths differ per service because they were written independently: the mandate engine,
// merchant API and MCP adapter expose /health, while the x402 gateway namespaces its probe
// under /api/v1/mesh/health. Rather than pretend they agree, the registry records what each one
// actually serves.

export type MeshServiceId =
  | "mcpServer"
  | "merchantApi"
  | "mandateEngine"
  | "x402Gateway";

export interface MeshServiceDescriptor {
  readonly serviceId: MeshServiceId;
  readonly displayName: string;
  readonly healthPath: string;
  readonly composePort: number;
  readonly packagePath: string;
}

export const meshServiceRegistry: readonly MeshServiceDescriptor[] = [
  {
    serviceId: "mcpServer",
    displayName: "MCP Server",
    healthPath: "/health",
    composePort: 4001,
    packagePath: "packages/mcpServer",
  },
  {
    serviceId: "merchantApi",
    displayName: "Merchant API",
    healthPath: "/health",
    composePort: 4002,
    packagePath: "packages/merchantApi",
  },
  {
    serviceId: "x402Gateway",
    displayName: "x402 Gateway",
    healthPath: "/api/v1/mesh/health",
    composePort: 4003,
    packagePath: "packages/x402Gateway",
  },
  {
    serviceId: "mandateEngine",
    displayName: "Mandate Engine",
    healthPath: "/health",
    composePort: 8000,
    packagePath: "packages/mandateEngine",
  },
];

export const meshServicesById: Readonly<Record<string, MeshServiceDescriptor>> =
  Object.fromEntries(meshServiceRegistry.map((service) => [service.serviceId, service]));
