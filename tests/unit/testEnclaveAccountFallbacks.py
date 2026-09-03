"""Unit tests pinning the camelCase/snake_case account-resolution fallbacks in
calculate_route_splits (arithmeticEnclave L155-L157).

Each of the three lines resolves WHICH Razorpay account is named in the settlement
split manifest, via `camelCaseParam or kwargs.get(snake_case, ...)`. If the `or`
degrades to `and`, supplying only the snake_case spelling yields None instead of the
account, and the real-world consequence is a payout routed to no account (or the wrong
one). No prior test called this function with only the snake_case spelling, so those
mutants survived. These tests supply each spelling independently and assert the exact
account identifier that lands in the returned RouteSplitResult.
"""

from razoragentMesh.packages.mandateEngine.verification.arithmeticEnclave import (
    calculate_route_splits,
)


def testMerchantAccountCamelSpellingResolves() -> None:
    """camelCase merchantAccount must win. Kills L155 `or`->`and`: under `and`,
    "acc_camel_m" and kwargs.get(...) collapses to the param default, misrouting the
    merchant payout to the wrong settlement account."""
    result = calculate_route_splits(orderPaise=100000, merchantAccount="acc_camel_m")
    assert result.merchantAccount == "acc_camel_m"


def testMerchantAccountSnakeSpellingResolves() -> None:
    """snake_case merchant_account must still route the merchant payout. This is the
    case nothing tested. Kills L155 `or`->`and`: under `and`, None and <acct> is None,
    so the merchant is paid to no account at all."""
    result = calculate_route_splits(orderPaise=100000, merchant_account="acc_snake_m")
    assert result.merchantAccount == "acc_snake_m"


def testLogisticsAccountCamelSpellingResolves() -> None:
    """camelCase logisticsAccount must win. Kills L157 `or`->`and`: under `and` the
    logistics leg would settle to the default account rather than the one supplied."""
    result = calculate_route_splits(orderPaise=100000, logisticsAccount="acc_camel_l")
    assert result.logisticsAccount == "acc_camel_l"


def testLogisticsAccountSnakeSpellingResolves() -> None:
    """snake_case logistics_account must still route the logistics leg. Untested case.
    Kills L157 `or`->`and`: under `and`, None and <acct> is None, sending the logistics
    settlement to no account."""
    result = calculate_route_splits(orderPaise=100000, logistics_account="acc_snake_l")
    assert result.logisticsAccount == "acc_snake_l"


def testProtocolAccountCamelSpellingResolves() -> None:
    """camelCase protocolAccount must win over the whole kwargs fallback chain. Kills
    L156 `or`->`and`: under `and` the protocol fee would be booked to the param default
    instead of the account the caller named."""
    result = calculate_route_splits(orderPaise=100000, protocolAccount="acc_camel_p")
    assert result.protocolFeeAccount == "acc_camel_p"


def testProtocolAccountSnakeSpellingResolves() -> None:
    """snake_case protocol_account (the declared parameter) must route the protocol fee.
    Untested case. Kills L156 `or`->`and`: under `and`, None and <chain> is None, so the
    protocol fee settles to no account."""
    result = calculate_route_splits(orderPaise=100000, protocol_account="acc_snake_p")
    assert result.protocolFeeAccount == "acc_snake_p"


def testProtocolAccountFeeAccountKwargFallback() -> None:
    """Second rung of L156's nested fallback: protocolFeeAccount kwarg is honoured when
    protocolAccount/protocol_account are absent. Kills L156 `or`->`and`, which would
    null the account, and pins the exact nesting order of the kwargs.get defaults."""
    result = calculate_route_splits(orderPaise=100000, protocolFeeAccount="acc_kw_fee")
    assert result.protocolFeeAccount == "acc_kw_fee"


def testProtocolAccountFeeAccountSnakeKwargFallback() -> None:
    """Third rung of L156's nested fallback: protocol_fee_account kwarg is honoured when
    the two higher-priority spellings are absent. Kills L156 `or`->`and` on the deepest
    default branch, which would otherwise route the protocol fee to None."""
    result = calculate_route_splits(
        orderPaise=100000, protocol_fee_account="acc_kw_snake_fee"
    )
    assert result.protocolFeeAccount == "acc_kw_snake_fee"
