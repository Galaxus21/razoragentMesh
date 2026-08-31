"use client";

import { useCallback, useState } from "react";
import type { FieldViolation } from "@/lib/sdkParameterValidation";
import type { SdkInvocationResult } from "@/types/sdkConsoleTypes";

const invokeEndpoint = "/api/demo/invoke";
const unprocessableStatus = 422;

interface InvocationErrorBody {
  readonly error?: string;
  readonly violations?: readonly FieldViolation[];
}

export interface UseSdkInvocationResult {
  readonly isRunning: boolean;
  readonly result: SdkInvocationResult | null;
  readonly errorMessage: string | null;
  readonly violations: readonly FieldViolation[];
  readonly invoke: (
    methodId: string,
    parameters: Readonly<Record<string, string>>
  ) => Promise<void>;
  readonly reset: () => void;
}

export function useSdkInvocation(): UseSdkInvocationResult {
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [result, setResult] = useState<SdkInvocationResult | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [violations, setViolations] = useState<readonly FieldViolation[]>([]);

  const reset = useCallback(() => {
    setResult(null);
    setErrorMessage(null);
    setViolations([]);
  }, []);

  const invoke = useCallback(
    async (methodId: string, parameters: Readonly<Record<string, string>>) => {
      setIsRunning(true);
      setErrorMessage(null);
      setViolations([]);

      try {
        const response = await fetch(invokeEndpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ methodId, parameters }),
        });

        if (!response.ok) {
          const body = (await response.json().catch(() => ({}))) as InvocationErrorBody;
          if (response.status === unprocessableStatus && body.violations) {
            setViolations(body.violations);
          }
          setErrorMessage(body.error ?? `Request failed with HTTP ${response.status}`);
          setResult(null);
          return;
        }

        setResult((await response.json()) as SdkInvocationResult);
      } catch (error) {
        // A transport failure here means the dashboard itself could not be reached, which is a
        // different problem from the mesh refusing a call -- so it is reported separately.
        setErrorMessage((error as Error).message);
        setResult(null);
      } finally {
        setIsRunning(false);
      }
    },
    []
  );

  return { isRunning, result, errorMessage, violations, invoke, reset };
}
