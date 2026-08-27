"""Property-Based Test Suite: Rubinstein-Ståhl Monotonic Negotiation FSM.

Verifies:
1. Acceptance of valid monotonic concession turn sequences (buyer bids non-decreasing, seller asks non-increasing).
2. Strict rejection of buyer bid decreases via NonMonotonicConcessionViolation with zero state mutation.
3. Strict rejection of seller ask increases via NonMonotonicConcessionViolation with zero state mutation.
4. Turn progression micro-metering (exact 50 paise debit per turn).
5. Turn limit exhaustion on turn 5 and rejection of turns > 5.
6. Seller counter-ask monotonic concessions and cost floor protection.
7. Spread computation non-negativity and convergence invariants.
"""

from hypothesis import given, settings, strategies as st
import pytest

try:
    from razoragentMesh.packages.x402Gateway.src.negotiation.bidStateMachine import (
        NegotiationStatus,
        RubinsteinStahlNegotiator,
    )
    from razoragentMesh.packages.x402Gateway.src.negotiation.convergenceChecker import (
        checkConvergence,
        computeSpread,
        validateMonotonicity,
    )
    from razoragentMesh.packages.x402Gateway.src.negotiation.marginEvaluator import (
        computeSellerCounterAsk,
        evaluateMargin,
    )
    from razoragentMesh.packages.x402Gateway.src.gatewayExceptions import (
        NegotiationExhaustedException,
        NonMonotonicConcessionViolation,
    )
except ModuleNotFoundError:
    from packages.x402Gateway.src.negotiation.bidStateMachine import (
        NegotiationStatus,
        RubinsteinStahlNegotiator,
    )
    from packages.x402Gateway.src.negotiation.convergenceChecker import (
        checkConvergence,
        computeSpread,
        validateMonotonicity,
    )
    from packages.x402Gateway.src.negotiation.marginEvaluator import (
        computeSellerCounterAsk,
        evaluateMargin,
    )
    from packages.x402Gateway.src.gatewayExceptions import (
        NegotiationExhaustedException,
        NonMonotonicConcessionViolation,
    )


# Custom Composite Strategies
@st.composite
def monotonic_turn_sequence_strategy(draw: st.DrawFn) -> list[tuple[int, int]]:
    """Generates 1 to 5 turns with buyer bids strictly non-decreasing and seller asks strictly non-increasing (both > 0)."""
    num_turns = draw(st.integers(min_value=1, max_value=5))
    initial_buyer = draw(st.integers(min_value=10000, max_value=500000))
    initial_seller = draw(st.integers(min_value=initial_buyer, max_value=1000000))

    turns = [(initial_buyer, initial_seller)]
    current_buyer = initial_buyer
    current_seller = initial_seller

    for _ in range(1, num_turns):
        buyer_concession = draw(st.integers(min_value=0, max_value=50000))
        seller_concession = draw(st.integers(min_value=0, max_value=50000))
        current_buyer += buyer_concession
        current_seller = max(1, current_seller - seller_concession)
        turns.append((current_buyer, current_seller))

    return turns


class TestPropertyNegotiationFsm:
    """Property tests for Rubinstein-Ståhl bargaining state machine."""

    @settings(max_examples=1000, deadline=None)
    @given(turns=monotonic_turn_sequence_strategy())
    def test_property_monotonic_concession_acceptance_and_fees(
        self, turns: list[tuple[int, int]]
    ) -> None:
        """Property: Any monotonic concession sequence is accepted and debits exactly 50 paise per turn."""
        negotiator = RubinsteinStahlNegotiator(
            skuId="SKU-TEST-001",
            quantity=10,
            escrowBalancePaise=5000,
            sellerCostFloorPaise=10000,
        )

        for turn_idx, (buyer_bid, seller_ask) in enumerate(turns, start=1):
            res = negotiator.executeTurn(turn_idx, buyer_bid, seller_ask)
            assert res.turnNumber == turn_idx
            assert res.buyerBidPaise == buyer_bid
            assert res.sellerAskPaise == seller_ask
            assert res.spreadPaise == max(0, seller_ask - buyer_bid)
            assert res.isConverged == (buyer_bid >= seller_ask)
            assert res.cumulativeMicroFeesPaise == 50 * turn_idx

        num_turns = len(turns)
        assert negotiator.escrowBalancePaise == 5000 - (50 * num_turns)
        assert negotiator.cumulativeMicroFeesPaise == 50 * num_turns
        assert len(negotiator.turnHistory) == num_turns

        last_buyer, last_seller = turns[-1]
        if last_buyer >= last_seller:
            assert negotiator.status == NegotiationStatus.CONVERGED
        elif num_turns == 5:
            assert negotiator.status == NegotiationStatus.NEGOTIATION_EXHAUSTED
        else:
            assert negotiator.status == NegotiationStatus.IN_PROGRESS

    @settings(max_examples=1000, deadline=None)
    @given(
        initial_buyer=st.integers(min_value=50000, max_value=500000),
        initial_seller=st.integers(min_value=500000, max_value=1000000),
        decrease=st.integers(min_value=1, max_value=40000),
        seller_concession=st.integers(min_value=0, max_value=10000),
    )
    def test_property_non_monotonic_buyer_bid_violation_and_state_unmutated(
        self, initial_buyer: int, initial_seller: int, decrease: int, seller_concession: int
    ) -> None:
        """Property: Buyer bid decrease raises NonMonotonicConcessionViolation with zero state mutation."""
        negotiator = RubinsteinStahlNegotiator(
            skuId="SKU-TEST-002",
            quantity=5,
            escrowBalancePaise=5000,
        )
        negotiator.executeTurn(1, initial_buyer, initial_seller)

        pre_escrow = negotiator.escrowBalancePaise
        pre_fees = negotiator.cumulativeMicroFeesPaise
        pre_history_len = len(negotiator.turnHistory)
        pre_status = negotiator.status

        bad_buyer_bid = initial_buyer - decrease
        seller_ask = max(1, initial_seller - seller_concession)

        with pytest.raises(NonMonotonicConcessionViolation) as exc_info:
            negotiator.executeTurn(2, bad_buyer_bid, seller_ask)

        assert "Buyer bid cannot decrease" in str(exc_info.value)

        # Assert zero state mutation
        assert negotiator.escrowBalancePaise == pre_escrow
        assert negotiator.cumulativeMicroFeesPaise == pre_fees
        assert len(negotiator.turnHistory) == pre_history_len
        assert negotiator.status == pre_status

    @settings(max_examples=1000, deadline=None)
    @given(
        initial_buyer=st.integers(min_value=50000, max_value=500000),
        initial_seller=st.integers(min_value=500000, max_value=1000000),
        buyer_concession=st.integers(min_value=0, max_value=10000),
        increase=st.integers(min_value=1, max_value=50000),
    )
    def test_property_non_monotonic_seller_ask_violation_and_state_unmutated(
        self, initial_buyer: int, initial_seller: int, buyer_concession: int, increase: int
    ) -> None:
        """Property: Seller ask increase raises NonMonotonicConcessionViolation with zero state mutation."""
        negotiator = RubinsteinStahlNegotiator(
            skuId="SKU-TEST-003",
            quantity=5,
            escrowBalancePaise=5000,
        )
        negotiator.executeTurn(1, initial_buyer, initial_seller)

        pre_escrow = negotiator.escrowBalancePaise
        pre_fees = negotiator.cumulativeMicroFeesPaise
        pre_history_len = len(negotiator.turnHistory)
        pre_status = negotiator.status

        buyer_bid = initial_buyer + buyer_concession
        bad_seller_ask = initial_seller + increase

        with pytest.raises(NonMonotonicConcessionViolation) as exc_info:
            negotiator.executeTurn(2, buyer_bid, bad_seller_ask)

        assert "Seller ask cannot increase" in str(exc_info.value)

        # Assert zero state mutation
        assert negotiator.escrowBalancePaise == pre_escrow
        assert negotiator.cumulativeMicroFeesPaise == pre_fees
        assert len(negotiator.turnHistory) == pre_history_len
        assert negotiator.status == pre_status

    @settings(max_examples=500, deadline=None)
    @given(
        initial_ask=st.integers(min_value=100000, max_value=10**8),
        cost_floor=st.integers(min_value=50000, max_value=100000),
        data=st.data(),
        turn_index=st.integers(min_value=1, max_value=20),
    )
    def test_property_seller_counter_ask_monotonicity_and_floor(
        self, initial_ask: int, cost_floor: int, data: st.DataObject, turn_index: int
    ) -> None:
        """Property: Seller counter-ask never breaches cost floor and is non-increasing with turns."""
        buyer_bid = data.draw(st.integers(min_value=1, max_value=initial_ask))

        counter_ask = computeSellerCounterAsk(
            initialAskPaise=initial_ask,
            buyerBidPaise=buyer_bid,
            turnIndex=turn_index,
            stepConcessionPaise=500,
            costFloorPaise=cost_floor,
        )
        assert counter_ask <= initial_ask
        assert counter_ask >= cost_floor

        # Concessions are non-increasing with subsequent turns for fixed buyer bid
        next_counter_ask = computeSellerCounterAsk(
            initialAskPaise=initial_ask,
            buyerBidPaise=buyer_bid,
            turnIndex=turn_index + 1,
            stepConcessionPaise=500,
            costFloorPaise=cost_floor,
        )
        assert next_counter_ask <= counter_ask

    @settings(max_examples=1000, deadline=None)
    @given(
        buyer_bid=st.integers(min_value=0, max_value=10**9),
        seller_ask=st.integers(min_value=0, max_value=10**9),
    )
    def test_property_spread_and_convergence_invariants(
        self, buyer_bid: int, seller_ask: int
    ) -> None:
        """Property: Spread is non-negative and is zero iff converged."""
        spread = computeSpread(sellerAskPaise=seller_ask, buyerBidPaise=buyer_bid)
        converged = checkConvergence(buyerBidPaise=buyer_bid, sellerAskPaise=seller_ask)

        assert spread == max(0, seller_ask - buyer_bid)
        assert spread >= 0
        assert (spread == 0) == (buyer_bid >= seller_ask)
        assert converged == (buyer_bid >= seller_ask)

    @settings(max_examples=200, deadline=None)
    @given(
        initial_buyer=st.integers(min_value=10000, max_value=50000),
        initial_seller=st.integers(min_value=100000, max_value=200000),
    )
    def test_property_turn_limit_exhaustion_on_turn_5_and_rejection_on_turn_6(
        self, initial_buyer: int, initial_seller: int
    ) -> None:
        """Property: Non-converged negotiation marks status NEGOTIATION_EXHAUSTED on turn 5 and rejects turn 6."""
        negotiator = RubinsteinStahlNegotiator(
            skuId="SKU-EXHAUST-001",
            quantity=1,
            escrowBalancePaise=5000,
        )
        # Execute 5 turns where buyer < seller
        for turn in range(1, 6):
            res = negotiator.executeTurn(turn, initial_buyer + (turn * 100), initial_seller - (turn * 100))
            assert not res.isConverged

        assert negotiator.status == NegotiationStatus.NEGOTIATION_EXHAUSTED

        # Turn 6 must raise NegotiationExhaustedException
        with pytest.raises(NegotiationExhaustedException):
            negotiator.executeTurn(6, initial_buyer + 1000, initial_seller - 1000)
