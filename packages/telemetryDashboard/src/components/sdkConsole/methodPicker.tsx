"use client";

import React from "react";
import { AlertTriangle } from "lucide-react";
import type { SdkMethodDescriptor } from "@/types/sdkConsoleTypes";

export interface MethodPickerProps {
  readonly methods: readonly SdkMethodDescriptor[];
  readonly selectedMethodId: string;
  readonly onSelect: (methodId: string) => void;
}

export function MethodPicker({
  methods,
  selectedMethodId,
  onSelect,
}: MethodPickerProps): React.JSX.Element {
  return (
    <ul className="space-y-1">
      {methods.map((method) => {
        const isSelected = method.methodId === selectedMethodId;
        return (
          <li key={method.methodId}>
            <button
              type="button"
              onClick={() => onSelect(method.methodId)}
              className={`w-full rounded-md border-l-2 px-2.5 py-2 text-left transition-colors cursor-pointer ${
                isSelected
                  ? "border-accentPrimary bg-bgSurfaceHover"
                  : "border-transparent hover:bg-bgSurfaceHover"
              }`}
            >
              <span className="block font-mono text-body-sm text-textPrimary">
                {method.methodName}
              </span>
              <span className="mt-0.5 block text-[11px] leading-snug text-textMuted">
                {method.transport}
              </span>
              {method.sideEffectWarning && (
                <span className="mt-1 inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide text-statusWarning">
                  <AlertTriangle className="h-3 w-3" />
                  Mutates state
                </span>
              )}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
