"""Property-Based Test Suite for Canonical GSTIN Luhn Mod-36 Validator.

Tests:
1. Valid 14-char prefix checksum round-trip across all 38 Indian state codes (01-38) and entity types.
2. Full Radix-36 single-character mutation falsification: flipping any character at any of the 15
   positions to any of the 35 alternate base-36 characters strictly fails verification.
3. Case-insensitivity and whitespace trimming invariance in computeGstinChecksum.
4. Input bounds and invalid length / non-base-36 character exception guarantees.
5. Statutory state code bounds (01-38 valid; 00, 39-99 rejected).
"""

import re
import pytest
from hypothesis import assume, given, settings, Verbosity, strategies as st

try:
    from razoragentMesh.packages.mandateEngine.tax.gstinValidator import (
        computeGstinChecksum,
        gstCharsTable,
        gstinLength,
        gstinPrefixLength,
        gstinRegexPattern,
        validateGstin,
    )
except ModuleNotFoundError:
    from packages.mandateEngine.tax.gstinValidator import (
        computeGstinChecksum,
        gstCharsTable,
        gstinLength,
        gstinPrefixLength,
        gstinRegexPattern,
        validateGstin,
    )


# ---------------------------------------------------------------------------
# Hypothesis Strategies for Statutory GSTIN Components
# ---------------------------------------------------------------------------

state_code_strategy = st.integers(min_value=1, max_value=38).map(lambda n: f"{n:02d}")
pan_first5_strategy = st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ", min_size=5, max_size=5)
pan_digits_strategy = st.text(alphabet="0123456789", min_size=4, max_size=4)
pan_last_letter_strategy = st.sampled_from("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
entity_code_strategy = st.sampled_from("123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ")
char_z_strategy = st.just("Z")


@st.composite
def valid_gstin_prefix_strategy(draw: st.DrawFn) -> str:
    """Generates valid 14-character statutory Indian GSTIN prefixes."""
    state = draw(state_code_strategy)
    pan5 = draw(pan_first5_strategy)
    pan4 = draw(pan_digits_strategy)
    pan_last = draw(pan_last_letter_strategy)
    entity = draw(entity_code_strategy)
    z = draw(char_z_strategy)
    return f"{state}{pan5}{pan4}{pan_last}{entity}{z}"


@st.composite
def valid_gstin_strategy(draw: st.DrawFn) -> str:
    """Generates canonical 15-character Indian GSTINs with computed Luhn Mod-36 check digits."""
    prefix = draw(valid_gstin_prefix_strategy())
    check_char = computeGstinChecksum(prefix)
    return prefix + check_char


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------

class TestGstinLuhnMod36Properties:
    """Hypothesis test suite verifying Luhn Mod-36 mathematical and validation invariants."""

    @settings(max_examples=1000, deadline=None)
    @given(prefix=valid_gstin_prefix_strategy())
    def test_property_valid_gstin_roundtrip(self, prefix: str) -> None:
        """For any valid 14-character GSTIN prefix across all states (01-38) and entity types,
        the computed checksum character satisfies validateGstin() == True."""
        assert len(prefix) == gstinPrefixLength
        check_char = computeGstinChecksum(prefix)
        assert check_char in gstCharsTable
        assert len(check_char) == 1

        full_gstin = prefix + check_char
        assert len(full_gstin) == gstinLength
        assert validateGstin(full_gstin) is True

    @settings(max_examples=200, deadline=None)
    @given(gstin=valid_gstin_strategy())
    def test_property_single_char_mutation_all_positions_exhaustive(self, gstin: str) -> None:
        """Exhaustive check: flipping ANY single character at ANY of the 15 positions to ANY
        of the 35 alternate base-36 characters strictly causes validateGstin() to return False
        (15 * 35 = 525 mutations checked per generated GSTIN)."""
        assert validateGstin(gstin) is True

        for pos in range(gstinLength):
            orig_char = gstin[pos]
            for alt_char in gstCharsTable:
                if alt_char == orig_char:
                    continue
                mutated = gstin[:pos] + alt_char + gstin[pos + 1 :]
                assert len(mutated) == gstinLength
                assert (
                    validateGstin(mutated) is False
                ), f"Failed to reject single-char mutation at pos {pos}: '{orig_char}' -> '{alt_char}' in {mutated}"

    @settings(max_examples=1000, deadline=None)
    @given(
        gstin=valid_gstin_strategy(),
        pos=st.integers(min_value=0, max_value=14),
        alt_char=st.sampled_from(gstCharsTable),
    )
    def test_property_single_char_mutation_sampled(self, gstin: str, pos: int, alt_char: str) -> None:
        """Sampled property check: randomly selected single-character mutation strictly falsifies validation."""
        assume(gstin[pos] != alt_char)
        mutated = gstin[:pos] + alt_char + gstin[pos + 1 :]
        assert validateGstin(mutated) is False

    @settings(max_examples=500, deadline=None)
    @given(prefix=valid_gstin_prefix_strategy())
    def test_property_checksum_determinism_case_and_whitespace(self, prefix: str) -> None:
        """computeGstinChecksum is purely deterministic, case-insensitive, and ignores leading/trailing whitespace."""
        c1 = computeGstinChecksum(prefix)
        c2 = computeGstinChecksum(prefix.lower())
        c3 = computeGstinChecksum(f"  {prefix}  \t\n")
        assert c1 == c2 == c3
        assert c1 in gstCharsTable

    @settings(max_examples=500, deadline=None)
    @given(invalid_length_str=st.text(alphabet=gstCharsTable).filter(lambda s: len(s.strip()) != 14))
    def test_property_compute_checksum_invalid_length_raises(self, invalid_length_str: str) -> None:
        """computeGstinChecksum strictly raises ValueError when input prefix length != 14."""
        with pytest.raises(ValueError):
            computeGstinChecksum(invalid_length_str)

    @settings(max_examples=500, deadline=None)
    @given(
        prefix=valid_gstin_prefix_strategy(),
        bad_pos=st.integers(min_value=0, max_value=13),
        bad_char=st.sampled_from("!@#$%^&*()-_=+[]{}|;:'\",.<>/?`~ \t\n\r"),
    )
    def test_property_compute_checksum_non_base36_char_raises(self, prefix: str, bad_pos: int, bad_char: str) -> None:
        """computeGstinChecksum strictly raises ValueError if non-base-36 symbols are present in prefix."""
        bad_prefix = prefix[:bad_pos] + bad_char + prefix[bad_pos + 1 :]
        with pytest.raises(ValueError):
            computeGstinChecksum(bad_prefix)

    @settings(max_examples=500, deadline=None)
    @given(
        invalid_state=st.one_of(
            st.just("00"),
            st.integers(min_value=39, max_value=99).map(lambda n: f"{n:02d}"),
        ),
        pan5=pan_first5_strategy,
        pan4=pan_digits_strategy,
        pan_last=pan_last_letter_strategy,
        entity=entity_code_strategy,
        z=char_z_strategy,
    )
    def test_property_invalid_state_codes_fail_validation(
        self, invalid_state: str, pan5: str, pan4: str, pan_last: str, entity: str, z: str
    ) -> None:
        """GSTINs with invalid state codes (00 or 39-99) fail validateGstin() even with matching check character."""
        prefix = f"{invalid_state}{pan5}{pan4}{pan_last}{entity}{z}"
        check = computeGstinChecksum(prefix)
        gstin = prefix + check
        assert validateGstin(gstin) is False
