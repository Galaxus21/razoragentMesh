// Builds and verifies a complete AP2 mandate chain, then breaks it on purpose.
//
// This program talks to nothing. Signing and hash-chaining are local Ed25519 operations, so the
// whole of INV-02 can be demonstrated without Redis, Qdrant or a single running service -- which
// is why CI executes this file on every push rather than merely typechecking it. If the chain
// ever stops verifying, or a tampered cart ever starts verifying, this exits non-zero.
//
// The guide at docs/buyer-sdk.mdx transcludes the regions below. Edit the code, not the prose.

import {
  AgentKeyManager,
  createSignedCartMandate,
  createSignedExecutionMandate,
  createSignedIntentMandate,
  verifyMandateChain,
  type CartMandate,
  type ExecutionMandate,
  type IntentMandate,
} from "../../packages/buyerSdkTs/src/index.js";

// One cotton shirt line, priced so the arithmetic below is checkable by hand: two units at
// 1,590.00 each, a 10% festive concession, and 12% GST on what remains.
const skuId = "sku_cotton_oxford_shirt";
const hsnCodeApparel = "6205";
const quantity = 2;
const unitPricePaise = 159000;
const lineTotalPaise = 318000;
const discountPaise = 31800;
const taxableSubtotalPaise = 286200;
const gstRatePercent = 12;
const cgstPaise = 17172;
const sgstPaise = 17172;
const igstPaise = 0;
const totalTaxPaise = 34344;
const shippingPaise = 0;
const totalPaise = 320544;

// Karnataka on both sides of the transaction, so the tax splits CGST + SGST and IGST stays zero.
// A different buyer state code here is what would move the whole amount into igstPaise.
const merchantGstin = "29AABCU9603R1ZM";
const merchantStateCode = "29";
const buyerDeliveryStateCode = "29";
const buyerDeliveryPincode = "560001";

const maxBudgetPaise = 5000000;
const singleTransactionLimitPaise = 800000;
const upiCircleDelegationToken = "upi_circle_delegation_a41c";
const inventoryLockToken = "lock_7f21c4a9";
const lockTtlMilliseconds = 60000;
const tamperReductionPaise = 50000;

// #region intent
function buildIntentMandate(
  userSigner: AgentKeyManager,
  delegatedAgentDid: string
): IntentMandate {
  // Signed by the human principal, not by the agent. The budget ceiling lives here so that the
  // limit travels with the authorization -- an agent that could edit its own ceiling has none.
  return createSignedIntentMandate(
    {
      mandateId: "mandate_intent_7f21c4",
      delegatedAgentDid,
      maxBudgetPaise,
      singleTransactionLimitPaise,
      upiCircleDelegationToken,
      authorizedCategories: ["apparel"],
    },
    userSigner
  );
}
// #endregion intent

// #region cart
function buildCartMandate(merchantSigner: AgentKeyManager): CartMandate {
  // Signed by the merchant enclave. The buyer agent receives this over the wire and verifies it;
  // it never produces one. The lock token and its expiry are what bind the cart to reserved stock.
  return createSignedCartMandate(
    {
      cartId: "cart_7f21c4",
      merchantGstin,
      merchantStateCode,
      buyerDeliveryPincode,
      buyerDeliveryStateCode,
      items: [
        { skuId, hsnCode: hsnCodeApparel, quantity, unitPricePaise, lineTotalPaise, gstRatePercent },
      ],
      taxableSubtotalPaise,
      taxBreakdown: { cgstPaise, sgstPaise, igstPaise, totalTaxPaise },
      shippingPaise,
      discountPaise,
      totalPaise,
      inventoryLockToken,
      inventoryLockExpiresAt: Date.now() + lockTtlMilliseconds,
    },
    merchantSigner
  );
}
// #endregion cart

// #region execution
function buildExecutionMandate(
  intentMandate: IntentMandate,
  cartMandate: CartMandate,
  buyerSigner: AgentKeyManager
): ExecutionMandate {
  // The only link the buyer agent signs. It records the SHA-256 of each preceding mandate, so the
  // chain is verifiable by recomputation rather than by trusting whoever hands it over.
  return createSignedExecutionMandate(
    {
      executionId: "exec_7f21c4",
      intentMandate,
      cartMandate,
      settlementAmountPaise: cartMandate.totalPaise,
      upiCircleToken: intentMandate.upiCircleDelegationToken,
    },
    buyerSigner
  );
}
// #endregion execution

function reportChainState(label: string, verified: boolean): void {
  console.log(`${label}: ${verified ? "verified" : "rejected"}`);
}

function main(): void {
  const userSigner = AgentKeyManager.generate();
  const merchantSigner = AgentKeyManager.generate();
  const buyerSigner = AgentKeyManager.generate();

  const intentMandate = buildIntentMandate(userSigner, buyerSigner.getAgentDid());
  const cartMandate = buildCartMandate(merchantSigner);
  const executionMandate = buildExecutionMandate(intentMandate, cartMandate, buyerSigner);

  console.log("Buyer agent DID:", buyerSigner.getAgentDid());
  console.log("Settling:", executionMandate.settlementAmountPaise, "paise");
  console.log("Intent hash:", executionMandate.intentMandateHash);
  console.log("Cart hash:  ", executionMandate.cartMandateHash);

  // #region verify
  const intact = verifyMandateChain(intentMandate, cartMandate, executionMandate);

  // The same chain with the cart discounted after the fact. Nothing else changes -- the merchant
  // signature, the execution mandate and both hashes are the originals -- and that is the point:
  // the recorded cartMandateHash no longer matches what the cart now hashes to.
  //
  // Note the try/catch. verifyMandateChain is declared `=> boolean`, but it returns true or
  // throws MandateVerificationError; it never returns false. Writing `if (!verifyMandateChain(..))`
  // compiles and then never runs its else branch. Catch the error -- do not test the result.
  const tamperedCart = { ...cartMandate, totalPaise: cartMandate.totalPaise - tamperReductionPaise };
  let tampered = true;
  try {
    verifyMandateChain(intentMandate, tamperedCart, executionMandate);
  } catch {
    tampered = false;
  }
  // #endregion verify

  reportChainState("Chain as signed", intact);
  reportChainState("Chain after editing the cart", tampered);

  if (!intact || tampered) {
    throw new Error("INV-02 violated: the chain must verify as signed and fail once edited");
  }
  console.log("INV-02 holds: the chain verifies as signed and fails once edited.");
}

main();
