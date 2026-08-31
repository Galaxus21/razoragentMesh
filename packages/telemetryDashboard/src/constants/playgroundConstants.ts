// Visual language for a protocol run, following the published design canvas.
//
// The single most important rule here: REFUSED is NOT an error state. On the adversarial page a
// refusal is the win condition -- the mesh rejected an attack -- so it gets its own colour
// (accentPrimary) and is never rendered green like a success or red like a failure. FAILED is
// reserved for things that genuinely broke, such as an unreachable service.

import type { ProtocolStepStatus } from "@/types/protocolRunTypes";

export interface StatusPresentation {
  readonly label: string;
  readonly caption: string;
  readonly badgeClass: string;
  readonly dotClass: string;
  readonly accentBorderClass: string;
}

export const stepStatusPresentation: Readonly<Record<ProtocolStepStatus, StatusPresentation>> = {
  SUCCEEDED: {
    label: "SUCCEEDED",
    caption: "Step completed",
    badgeClass: "bg-statusSuccess/10 text-statusSuccess border-statusSuccess/30",
    dotClass: "bg-statusSuccess",
    accentBorderClass: "border-l-statusSuccess"
  },
  REFUSED: {
    label: "REFUSED",
    caption: "Protocol worked — the attack was rejected",
    badgeClass: "bg-accentPrimary/10 text-accentPrimary border-accentPrimary/30",
    dotClass: "bg-accentPrimary",
    accentBorderClass: "border-l-accentPrimary"
  },
  FAILED: {
    label: "FAILED",
    caption: "Something genuinely broke",
    badgeClass: "bg-statusError/10 text-statusError border-statusError/30",
    dotClass: "bg-statusError",
    accentBorderClass: "border-l-statusError"
  },
  RUNNING: {
    label: "RUNNING",
    caption: "In flight",
    badgeClass: "bg-statusInfo/10 text-statusInfo border-statusInfo/30",
    dotClass: "bg-statusInfo animate-pulseFast",
    accentBorderClass: "border-l-statusInfo"
  },
  PENDING: {
    label: "PENDING",
    caption: "Not started",
    badgeClass: "bg-surfaceContainer text-textMuted border-borderSubtle",
    dotClass: "bg-textMuted",
    accentBorderClass: "border-l-borderSubtle"
  }
};

export const runOutcomePresentation = {
  EXPECTED: {
    badgeClass: "bg-statusSuccess/10 text-statusSuccess border-statusSuccess/30",
    label: "AS EXPECTED"
  },
  UNEXPECTED: {
    badgeClass: "bg-statusError/10 text-statusError border-statusError/30",
    label: "UNEXPECTED"
  }
} as const;

export const scenarioKindPresentation = {
  HAPPY_PATH: {
    label: "HAPPY PATH",
    badgeClass: "bg-statusSuccess/10 text-statusSuccess border-statusSuccess/30"
  },
  ADVERSARIAL: {
    label: "ADVERSARIAL",
    badgeClass: "bg-accentPrimary/10 text-accentPrimary border-accentPrimary/30"
  }
} as const;

export const panelClass = "rounded-xl border border-borderSubtle bg-bgSurface shadow-sm";
export const stepperWidthClass = "w-[320px] shrink-0";
export const detailScrollClass = "max-h-[560px] overflow-y-auto custom-scrollbar";

export const runEndpointPath = "/api/demo/run";
export const hashPreviewLength = 16;

export const verifyIdleLabel = "Verify in your browser";
export const verifyPassLabel = "Signature verified in this tab";
export const verifyFailLabel = "Verification failed in this tab";
