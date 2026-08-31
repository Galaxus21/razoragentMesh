// Which steps each scenario runs, and in what order.
//
// Split out of runScenario.ts, which was carrying both the step lists and the execution loop and
// had grown past the repo's file-length limit. Keeping the lists here also makes the shape of the
// adversarial grid readable in one screen: every attack is the happy path with one thing changed.

import {
  scenarioBudgetBlocked,
  scenarioOversizedTransaction,
  scenarioReplayedSettlement,
  scenarioSettlementAmountMismatch,
  scenarioStaleDelegation,
  scenarioTamperedMandate
} from "@/constants/scenarioCatalog";
import { stepFetchQuote, stepReserveLock, stepVerifySla } from "./discoverySteps";
import {
  buildIntentStep,
  stepSignCart,
  stepSignExecution,
  stepTamperCart,
  stepVerifyChain
} from "./mandateSteps";
import { stepSettle } from "./settlementSteps";
import { stepInflateSettlementAmount, stepReplaySettlement } from "./adversarialSteps";
import type { ExecutableStep } from "./stepContext";

// Deliberately below any realistic cart total, so the budget gate is the thing that trips --
// not a coincidence of pricing.
const constrainedBudgetPaise = 50_000;
// A delegation that expired an hour ago: validly signed, no longer authoritative.
const expiredDelegationSeconds = -3_600;
// Comfortably above any cart the demo produces, so the overall budget is plainly not the thing
// that trips -- the per-transaction ceiling below it is.
const generousBudgetPaise = 50_000_000;
const tightTransactionLimitPaise = 1_000;
// Every adversarial scenario is the happy path with one thing changed, so a refusal is always
// produced by the same verifier the successful run uses.
const discoverySteps: readonly ExecutableStep[] = [stepFetchQuote, stepVerifySla, stepReserveLock];

export function buildScenarioSteps(scenarioId: string): readonly ExecutableStep[] {
  if (scenarioId === scenarioStaleDelegation) {
    return [
      ...discoverySteps,
      buildIntentStep({ validitySecondsOverride: expiredDelegationSeconds }),
      stepSignCart,
      stepSignExecution,
      stepVerifyChain
    ];
  }
  if (scenarioId === scenarioOversizedTransaction) {
    return [
      ...discoverySteps,
      buildIntentStep({
        budgetOverridePaise: generousBudgetPaise,
        singleTransactionLimitOverridePaise: tightTransactionLimitPaise
      }),
      stepSignCart,
      stepSignExecution,
      stepVerifyChain
    ];
  }
  if (scenarioId === scenarioSettlementAmountMismatch) {
    return [
      ...discoverySteps,
      buildIntentStep(),
      stepSignCart,
      stepSignExecution,
      stepInflateSettlementAmount,
      stepVerifyChain
    ];
  }
  if (scenarioId === scenarioReplayedSettlement) {
    return [
      ...discoverySteps,
      buildIntentStep(),
      stepSignCart,
      stepSignExecution,
      stepVerifyChain,
      stepSettle,
      stepReplaySettlement
    ];
  }
  if (scenarioId === scenarioBudgetBlocked) {
    return [
      stepFetchQuote,
      stepVerifySla,
      stepReserveLock,
      buildIntentStep({ budgetOverridePaise: constrainedBudgetPaise }),
      stepSignCart,
      stepSignExecution,
      stepVerifyChain
    ];
  }
  if (scenarioId === scenarioTamperedMandate) {
    return [
      stepFetchQuote,
      stepVerifySla,
      stepReserveLock,
      buildIntentStep(),
      stepSignCart,
      stepSignExecution,
      stepTamperCart,
      stepVerifyChain
    ];
  }
  return [
    stepFetchQuote,
    stepVerifySla,
    stepReserveLock,
    buildIntentStep(),
    stepSignCart,
    stepSignExecution,
    stepVerifyChain,
    stepSettle
  ];
}
