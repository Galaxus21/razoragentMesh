// Scenario metadata, kept free of server-only imports so the picker UI can render the catalog
// without pulling the driver (and the buyer SDK) into the client bundle.

import type { ScenarioSummary } from "@/types/protocolRunTypes";

export const scenarioHappyPath = "happyPath";
export const scenarioBudgetBlocked = "budgetBlocked";
export const scenarioTamperedMandate = "tamperedMandate";
export const scenarioStaleDelegation = "staleDelegation";
export const scenarioOversizedTransaction = "oversizedTransaction";
export const scenarioSettlementAmountMismatch = "settlementAmountMismatch";
export const scenarioReplayedSettlement = "replayedSettlement";

export const scenarioSummaries: ReadonlyArray<ScenarioSummary> = [
  {
    scenarioId: scenarioHappyPath,
    label: "Autonomous purchase, end to end",
    kind: "HAPPY_PATH",
    premise:
      "A buyer agent holding a signed spending delegation discovers a quote, verifies shipping, locks stock, and settles -- with no human in the loop.",
    expectedOutcome:
      "Every mandate in the Intent -> Cart -> Execution chain verifies, and the settlement saga completes.",
    invariants: ["Ed25519 canonical signatures", "Integer paise arithmetic"]
  },
  {
    scenarioId: scenarioBudgetBlocked,
    label: "Cart exceeds the delegated budget",
    kind: "ADVERSARIAL",
    premise:
      "The same flow, but the merchant's cart total is priced above the ceiling the user delegated in the Intent Mandate.",
    expectedOutcome:
      "The chain verifier refuses before any money moves. A refusal here is the correct result, not a failure.",
    invariants: ["AP2 budget gate"]
  },
  {
    scenarioId: scenarioTamperedMandate,
    label: "One byte of a signed cart is altered",
    kind: "ADVERSARIAL",
    premise:
      "After the merchant signs the Cart Mandate, a single field is modified in transit -- the classic man-in-the-middle edit.",
    expectedOutcome:
      "The Execution Mandate's recorded cart hash no longer matches the tampered cart, so verification refuses.",
    invariants: ["Ed25519 canonical signatures"]
  },
  {
    scenarioId: scenarioStaleDelegation,
    label: "A delegation that expired before it was used",
    kind: "ADVERSARIAL",
    premise:
      "The Intent Mandate is genuine and correctly signed by the user, but its validity window closed before the agent got around to spending. A captured delegation replayed a day later looks exactly like this.",
    expectedOutcome:
      "Chain verification compares the execution timestamp against the delegation's expiry and refuses. Signature validity is not the same as authority.",
    invariants: ["Delegation validity window"]
  },
  {
    scenarioId: scenarioOversizedTransaction,
    label: "Within the budget, over the per-transaction cap",
    kind: "ADVERSARIAL",
    premise:
      "The user delegated a generous overall budget but a much smaller single-transaction ceiling. The cart fits the first and breaks the second -- the shape of an agent draining a budget in one purchase instead of many.",
    expectedOutcome:
      "The per-transaction ceiling is enforced independently of the overall budget, so the run is refused with the budget still largely unspent.",
    invariants: ["Per-transaction ceiling", "AP2 budget gate"]
  },
  {
    scenarioId: scenarioSettlementAmountMismatch,
    label: "The agent asks to settle more than the cart",
    kind: "ADVERSARIAL",
    premise:
      "Every mandate is signed by the right party and the cart is untouched. The buyer agent alters only its own Execution Mandate to request a larger transfer -- the case where the compromised party is the agent, not the network.",
    expectedOutcome:
      "The settlement amount is checked against the signed cart total, so an agent cannot move more money than the cart it was handed.",
    invariants: ["Settlement matches the signed cart"]
  },
  {
    scenarioId: scenarioReplayedSettlement,
    label: "A captured settlement is submitted twice",
    kind: "ADVERSARIAL",
    premise:
      "The first settlement completes normally. The identical bundle is then submitted again, nonce and all, which is what a network attacker gets for free from one captured request.",
    expectedOutcome:
      "The engine's Redis nonce ledger has already spent that nonce and refuses the second submission, so the buyer is charged once. This scenario needs the mesh running: the ledger is server-side.",
    invariants: ["Anti-replay nonce ledger"]
  }
];

export function findScenarioSummary(scenarioId: string): ScenarioSummary | undefined {
  return scenarioSummaries.find((summary) => summary.scenarioId === scenarioId);
}
