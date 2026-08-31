// Probes every mesh service's liveness endpoint.
//
// Runs server-side because the browser reaches the dashboard, not the compose network: inside
// Docker the services resolve by service name, which a visitor's browser cannot resolve at all.

import { meshServiceRegistry } from "@/constants/meshServiceRegistry";
import { resolveServiceUrls } from "@/server/protocolDriver/driverConfig";
import type { MeshServiceId } from "@/constants/meshServiceRegistry";

export type MeshServiceHealth = "UP" | "DOWN";

export interface MeshServiceStatus {
  readonly serviceId: MeshServiceId;
  readonly health: MeshServiceHealth;
  readonly statusCode?: number;
  readonly latencyMs: number;
  readonly detail?: string;
}

const probeTimeoutMs = 2000;

function resolveBaseUrl(serviceId: MeshServiceId): string {
  const urls = resolveServiceUrls();
  if (serviceId === "mcpServer") {
    return urls.mcpServerUrl;
  }
  if (serviceId === "merchantApi") {
    return urls.merchantApiUrl;
  }
  if (serviceId === "x402Gateway") {
    return urls.x402GatewayUrl;
  }
  return urls.mandateEngineUrl;
}

async function probeOneService(serviceId: MeshServiceId, healthPath: string): Promise<MeshServiceStatus> {
  const startedAtMs = performance.now();
  try {
    const response = await fetch(`${resolveBaseUrl(serviceId)}${healthPath}`, {
      signal: AbortSignal.timeout(probeTimeoutMs),
      cache: "no-store",
    });
    return {
      serviceId,
      health: response.ok ? "UP" : "DOWN",
      statusCode: response.status,
      latencyMs: Math.round(performance.now() - startedAtMs),
      // A 404 here means the probe path is wrong, not that the service is dead. Saying so is
      // more useful than a bare red dot.
      ...(response.ok ? {} : { detail: `Probe returned HTTP ${response.status}` }),
    };
  } catch (error) {
    return {
      serviceId,
      health: "DOWN",
      latencyMs: Math.round(performance.now() - startedAtMs),
      detail: (error as Error).message,
    };
  }
}

export async function probeMeshServices(): Promise<readonly MeshServiceStatus[]> {
  // Probed concurrently: one unreachable service must not add its timeout to every other
  // service's wait, or a single dead container makes the whole page look slow.
  return Promise.all(
    meshServiceRegistry.map((service) => probeOneService(service.serviceId, service.healthPath))
  );
}
