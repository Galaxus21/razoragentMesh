"use client";

import { useCallback, useEffect, useState } from "react";
import type { MeshServiceStatus } from "@/server/meshHealth/probeMeshServices";

const healthEndpoint = "/api/mesh/health";
const refreshIntervalMs = 15_000;

export interface UseMeshHealthResult {
  readonly statuses: readonly MeshServiceStatus[];
  readonly isProbing: boolean;
  readonly errorMessage: string | null;
  readonly refresh: () => Promise<void>;
}

interface HealthResponseBody {
  readonly services: readonly MeshServiceStatus[];
}

export function useMeshHealth(): UseMeshHealthResult {
  const [statuses, setStatuses] = useState<readonly MeshServiceStatus[]>([]);
  const [isProbing, setIsProbing] = useState<boolean>(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setIsProbing(true);
    try {
      const response = await fetch(healthEndpoint, { cache: "no-store" });
      if (!response.ok) {
        throw new Error(`Health probe failed with HTTP ${response.status}`);
      }
      const body = (await response.json()) as HealthResponseBody;
      setStatuses(body.services);
      setErrorMessage(null);
    } catch (error) {
      // Leaves the previous statuses in place: a transient failure to reach the dashboard's own
      // route is not evidence that the mesh went down.
      setErrorMessage((error as Error).message);
    } finally {
      setIsProbing(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timerId = setInterval(() => {
      void refresh();
    }, refreshIntervalMs);
    return () => clearInterval(timerId);
  }, [refresh]);

  return { statuses, isProbing, errorMessage, refresh };
}
