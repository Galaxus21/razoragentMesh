"""Builds and verifies a complete AP2 mandate chain, then breaks it on purpose.

The Python counterpart of examples/typescript/mandateChain.ts, kept deliberately parallel so the
two can be read side by side. Like it, this program talks to nothing: signing and hash-chaining
are local Ed25519 operations, so the whole of INV-02 runs without Redis, Qdrant or a single
service. CI executes this file rather than merely importing it -- if the chain stops verifying,
or a tampered cart starts verifying, it exits non-zero.

One real difference from the TypeScript version is called out at the verification step below.

Run it with the SDK on the path:

    PYTHONPATH=packages/buyerSdkPy python examples/python/mandateChain.py

The guide at docs/buyer-sdk.mdx transcludes the regions below. Edit the code, not the prose.
"""

import time

from razoragent_buyer_sdk import (
    AgentKeyManager,
    CartItemSchema,
    CartMandate,
    ExecutionMandate,
    IntentMandate,
    TaxBreakdownSchema,
    createSignedCartMandate,
    createSignedExecutionMandate,
    createSignedIntentMandate,
    verifyMandateHashChain,
)

# One cotton shirt line, priced so the arithmetic is checkable by hand: two units at 1,590.00
# each, a 10% festive concession, and 12% GST on what remains.
skuId = "sku_cotton_oxford_shirt"
hsnCodeApparel = "6205"
quantity = 2
unitPricePaise = 159000
lineTotalPaise = 318000
discountPaise = 31800
taxableSubtotalPaise = 286200
gstRatePercent = 12
cgstPaise = 17172
sgstPaise = 17172
igstPaise = 0
totalTaxPaise = 34344
shippingPaise = 0
totalPaise = 320544

# Karnataka on both sides of the transaction, so the tax splits CGST + SGST and IGST stays zero.
# A different buyer state code here is what would move the whole amount into igstPaise.
merchantGstin = "29AABCU9603R1ZM"
merchantStateCode = "29"
buyerDeliveryStateCode = "29"
buyerDeliveryPincode = "560001"

maxBudgetPaise = 5000000
singleTransactionLimitPaise = 800000
upiCircleDelegationToken = "upi_circle_delegation_a41c"
inventoryLockToken = "lock_7f21c4a9"
lockTtlSeconds = 60
tamperReductionPaise = 50000


# region intent
def buildIntentMandate(userSigner: AgentKeyManager, delegatedAgentDid: str) -> IntentMandate:
    """Signed by the human principal, not by the agent.

    The budget ceiling lives here so the limit travels with the authorization -- an agent that
    could edit its own ceiling has none.
    """
    return createSignedIntentMandate(
        mandateId="mandate_intent_7f21c4",
        userKeyManager=userSigner,
        delegatedAgentDid=delegatedAgentDid,
        maxBudgetPaise=maxBudgetPaise,
        upiCircleDelegationToken=upiCircleDelegationToken,
        singleTransactionLimitPaise=singleTransactionLimitPaise,
        authorizedCategories=["apparel"],
    )
# endregion intent


# region cart
def buildCartMandate(merchantSigner: AgentKeyManager) -> CartMandate:
    """Signed by the merchant enclave.

    The buyer agent receives this over the wire and verifies it; it never produces one. The lock
    token and its expiry are what bind the cart to reserved stock.
    """
    return createSignedCartMandate(
        cartId="cart_7f21c4",
        merchantKeyManager=merchantSigner,
        merchantGstin=merchantGstin,
        merchantStateCode=merchantStateCode,
        buyerDeliveryPincode=buyerDeliveryPincode,
        buyerDeliveryStateCode=buyerDeliveryStateCode,
        items=[
            CartItemSchema(
                skuId=skuId,
                hsnCode=hsnCodeApparel,
                quantity=quantity,
                unitPricePaise=unitPricePaise,
                lineTotalPaise=lineTotalPaise,
                gstRatePercent=gstRatePercent,
            )
        ],
        taxableSubtotalPaise=taxableSubtotalPaise,
        taxBreakdown=TaxBreakdownSchema(
            cgstPaise=cgstPaise,
            sgstPaise=sgstPaise,
            igstPaise=igstPaise,
            totalTaxPaise=totalTaxPaise,
        ),
        shippingPaise=shippingPaise,
        discountPaise=discountPaise,
        totalPaise=totalPaise,
        inventoryLockToken=inventoryLockToken,
        inventoryLockExpiresAt=int(time.time()) + lockTtlSeconds,
    )
# endregion cart


# region execution
def buildExecutionMandate(
    intentMandate: IntentMandate,
    cartMandate: CartMandate,
    buyerSigner: AgentKeyManager,
) -> ExecutionMandate:
    """The only link the buyer agent signs.

    It records the SHA-256 of each preceding mandate, so the chain is verifiable by
    recomputation rather than by trusting whoever hands it over.
    """
    return createSignedExecutionMandate(
        executionId="exec_7f21c4",
        buyerKeyManager=buyerSigner,
        intentMandate=intentMandate,
        cartMandate=cartMandate,
        settlementAmountPaise=cartMandate.totalPaise,
        upiCircleToken=intentMandate.upiCircleDelegationToken,
    )
# endregion execution


def reportChainState(label: str, verified: bool) -> None:
    print(f"{label}: {'verified' if verified else 'rejected'}")


def main() -> None:
    userSigner = AgentKeyManager.generate()
    merchantSigner = AgentKeyManager.generate()
    buyerSigner = AgentKeyManager.generate()

    intentMandate = buildIntentMandate(userSigner, buyerSigner.getAgentDid())
    cartMandate = buildCartMandate(merchantSigner)
    executionMandate = buildExecutionMandate(intentMandate, cartMandate, buyerSigner)

    print("Buyer agent DID:", buyerSigner.getAgentDid())
    print("Settling:", executionMandate.settlementAmountPaise, "paise")
    print("Intent hash:", executionMandate.intentMandateHash)
    print("Cart hash:  ", executionMandate.cartMandateHash)

    # region verify
    intact = verifyMandateHashChain(intentMandate, cartMandate, executionMandate)

    # The same chain with the cart discounted after the fact. Nothing else changes -- the
    # merchant signature, the execution mandate and both hashes are the originals -- and that is
    # the point: the recorded cartMandateHash no longer matches what the cart now hashes to.
    #
    # raiseOnMismatch=False is where the two runtimes genuinely differ. Python lets you ask for
    # a boolean; TypeScript's verifyMandateChain is declared `=> boolean` but only ever returns
    # true or throws, so the equivalent line there has to be a try/except.
    tamperedCart = cartMandate.model_copy(
        update={"totalPaise": cartMandate.totalPaise - tamperReductionPaise}
    )
    tampered = verifyMandateHashChain(
        intentMandate, tamperedCart, executionMandate, raiseOnMismatch=False
    )
    # endregion verify

    reportChainState("Chain as signed", intact)
    reportChainState("Chain after editing the cart", tampered)

    if not intact or tampered:
        raise SystemExit("INV-02 violated: the chain must verify as signed and fail once edited")
    print("INV-02 holds: the chain verifies as signed and fails once edited.")


if __name__ == "__main__":
    main()
