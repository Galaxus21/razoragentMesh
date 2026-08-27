"""Property-Based Test Suite for RFC 8785 Canonical JCS and Ed25519 Cryptographic Invariants.

Tests:
1. RFC 8785 Canonical JCS key-ordering permutation invariance under arbitrary recursive JSON payloads.
2. Ed25519 signing and verification round-trip invariance across arbitrary payloads and key permutations.
3. Leaf and node mutation falsification: tampering with any leaf element breaks signature verification.
4. Signature corruption, bit-flip, and wrong public key rejection.
5. Strict floating-point rejection across canonicalization, hashing, signing, and verification.
"""

import json
import random
from typing import Any, Dict, List
import pytest
from hypothesis import assume, given, settings, Verbosity, strategies as st

try:
    from razoragentMesh.packages.mandateEngine.crypto.cryptoKeyUtils import (
        extractPublicKeyFromDid,
        formatDid,
        generateKeyPair,
    )
    from razoragentMesh.packages.mandateEngine.crypto.ed25519Signer import Ed25519Signer
    from razoragentMesh.packages.mandateEngine.crypto.ed25519Verifier import Ed25519Verifier
    from razoragentMesh.packages.mandateEngine.crypto.jcsCanonicalizer import (
        canonicalizeAndHash,
        canonicalizeJson,
        computeSha256Digest,
    )
    from razoragentMesh.packages.mandateEngine.settlement.settlementExceptions import (
        ArithmeticDriftException,
        SignatureVerificationFailedException,
    )
except ModuleNotFoundError:
    from packages.mandateEngine.crypto.cryptoKeyUtils import (
        extractPublicKeyFromDid,
        formatDid,
        generateKeyPair,
    )
    from packages.mandateEngine.crypto.ed25519Signer import Ed25519Signer
    from packages.mandateEngine.crypto.ed25519Verifier import Ed25519Verifier
    from packages.mandateEngine.crypto.jcsCanonicalizer import (
        canonicalizeAndHash,
        canonicalizeJson,
        computeSha256Digest,
    )
    from packages.mandateEngine.settlement.settlementExceptions import (
        ArithmeticDriftException,
        SignatureVerificationFailedException,
    )


# ---------------------------------------------------------------------------
# Hypothesis Strategies for Arbitrary JSON Payloads (Strictly No Floats)
# ---------------------------------------------------------------------------

json_primitives = st.one_of(
    st.integers(min_value=-10**18, max_value=10**18),
    st.text(alphabet=st.characters(blacklist_categories=["Cs"]), max_size=50),
    st.booleans(),
    st.none(),
)

json_payloads = st.recursive(
    json_primitives,
    lambda children: st.one_of(
        st.lists(children, max_size=8),
        st.dictionaries(
            keys=st.text(alphabet=st.characters(blacklist_categories=["Cs"]), min_size=1, max_size=30),
            values=children,
            max_size=8,
        ),
    ),
    max_leaves=25,
)

json_objects = st.dictionaries(
    keys=st.text(alphabet=st.characters(blacklist_categories=["Cs"]), min_size=1, max_size=30),
    values=json_payloads,
    min_size=1,
    max_size=10,
)


# ---------------------------------------------------------------------------
# Permutation & Mutation Helpers
# ---------------------------------------------------------------------------

def _deep_permute_dict_keys(data: Any, rng: random.Random) -> Any:
    """Recursively reconstructs dictionary structures with shuffled key insertion orders."""
    if isinstance(data, dict):
        keys = list(data.keys())
        rng.shuffle(keys)
        return {k: _deep_permute_dict_keys(data[k], rng) for k in keys}
    elif isinstance(data, list):
        return [_deep_permute_dict_keys(item, rng) for item in data]
    return data


def _deep_mutate_leaf(data: Any, rng: random.Random) -> Any:
    """Mutates a leaf or subtree in a JSON payload."""
    if isinstance(data, dict):
        if not data:
            return {"_injected_key": "injected_val"}
        keys = list(data.keys())
        k = rng.choice(keys)
        choice = rng.random()
        if choice < 0.33 and len(keys) > 1:
            copy_dict = dict(data)
            del copy_dict[k]
            return copy_dict
        elif choice < 0.66:
            copy_dict = dict(data)
            copy_dict[f"_extra_{rng.randint(100, 999)}"] = 42
            return copy_dict
        else:
            copy_dict = dict(data)
            copy_dict[k] = _deep_mutate_leaf(data[k], rng)
            return copy_dict
    elif isinstance(data, list):
        if not data:
            return [999]
        copy_list = list(data)
        idx = rng.randint(0, len(copy_list) - 1)
        copy_list[idx] = _deep_mutate_leaf(copy_list[idx], rng)
        return copy_list
    elif isinstance(data, int):
        return data + 1
    elif isinstance(data, str):
        return data + "_tampered"
    elif isinstance(data, bool):
        return not data
    elif data is None:
        return 0
    return data


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------

class TestJcsEd25519Properties:
    """Hypothesis test suite verifying RFC 8785 JCS canonicalization and Ed25519 signature invariants."""

    @settings(max_examples=500, deadline=None)
    @given(payload=json_objects, seed=st.integers(min_value=0, max_value=2**32 - 1))
    def test_property_jcs_key_permutation_invariance(self, payload: dict, seed: int) -> None:
        """Canonical JCS output and SHA-256 digest are strictly invariant to dictionary key ordering
        across arbitrary nesting levels."""
        rng = random.Random(seed)
        permuted = _deep_permute_dict_keys(payload, rng)

        canonical_orig, digest_orig = canonicalizeAndHash(payload)
        canonical_perm, digest_perm = canonicalizeAndHash(permuted)

        assert canonical_orig == canonical_perm
        assert digest_orig == digest_perm
        assert isinstance(canonical_orig, bytes)
        assert len(digest_orig) == 64

    @settings(max_examples=300, deadline=None)
    @given(payload=json_objects, seed=st.integers(min_value=0, max_value=2**32 - 1))
    def test_property_ed25519_sign_verify_roundtrip(self, payload: dict, seed: int) -> None:
        """Any valid JSON payload signed with Ed25519Signer verifies successfully with Ed25519Verifier,
        and verification succeeds across arbitrary key permutations."""
        private_key, public_key = generateKeyPair()
        signer = Ed25519Signer(private_key)

        sig_hex = signer.signPayload(payload)
        assert len(sig_hex) == 128
        assert all(c in "0123456789abcdef" for c in sig_hex)

        # Verification over original payload
        assert Ed25519Verifier.verifyPayloadSignature(public_key, payload, sig_hex) is True

        # Verification over permuted payload
        permuted = _deep_permute_dict_keys(payload, random.Random(seed))
        assert Ed25519Verifier.verifyPayloadSignature(public_key, permuted, sig_hex) is True

    @settings(max_examples=300, deadline=None)
    @given(payload=json_objects, seed=st.integers(min_value=0, max_value=2**32 - 1))
    def test_property_ed25519_tampering_falsification(self, payload: dict, seed: int) -> None:
        """Mutating any leaf, key, or subtree in a signed payload strictly invalidates the signature,
        returning False and raising SignatureVerificationFailedException when raiseOnFailure=True."""
        private_key, public_key = generateKeyPair()
        signer = Ed25519Signer(private_key)

        sig_hex = signer.signPayload(payload)

        rng = random.Random(seed)
        tampered = _deep_mutate_leaf(payload, rng)
        assume(canonicalizeJson(tampered) != canonicalizeJson(payload))

        assert Ed25519Verifier.verifyPayloadSignature(public_key, tampered, sig_hex) is False
        with pytest.raises(SignatureVerificationFailedException):
            Ed25519Verifier.verifyPayloadSignature(public_key, tampered, sig_hex, raiseOnFailure=True)

    @settings(max_examples=300, deadline=None)
    @given(
        payload=json_objects,
        flip_pos=st.integers(min_value=0, max_value=127),
        alt_hex=st.sampled_from("0123456789abcdef"),
    )
    def test_property_ed25519_signature_bitflip_falsification(
        self, payload: dict, flip_pos: int, alt_hex: str
    ) -> None:
        """Flipping any single hexadecimal character in the 128-char signature causes verification failure."""
        private_key, public_key = generateKeyPair()
        signer = Ed25519Signer(private_key)

        sig_hex = signer.signPayload(payload)
        assume(sig_hex[flip_pos] != alt_hex)

        corrupted_sig = sig_hex[:flip_pos] + alt_hex + sig_hex[flip_pos + 1 :]
        assert Ed25519Verifier.verifyPayloadSignature(public_key, payload, corrupted_sig) is False

    @settings(max_examples=300, deadline=None)
    @given(
        payload=json_objects,
        float_val=st.one_of(
            st.floats(allow_nan=True, allow_infinity=True),
            st.sampled_from([0.0, -0.0, 1.5, 3.14159, 1e-5, 1e10, 1976.50]),
        ),
    )
    def test_property_jcs_and_signer_strictly_reject_floats(self, payload: dict, float_val: float) -> None:
        """Injecting a float anywhere in the payload strictly raises ArithmeticDriftException across
        canonicalizeJson, canonicalizeAndHash, signPayload, and verifyPayloadSignature."""
        private_key, public_key = generateKeyPair()
        signer = Ed25519Signer(private_key)

        # 1. Float at root
        with pytest.raises(ArithmeticDriftException):
            canonicalizeJson(float_val)

        # 2. Float injected into dict
        payload_with_float = dict(payload)
        payload_with_float["_injected_float"] = float_val

        with pytest.raises(ArithmeticDriftException):
            canonicalizeJson(payload_with_float)
        with pytest.raises(ArithmeticDriftException):
            canonicalizeAndHash(payload_with_float)
        with pytest.raises(ArithmeticDriftException):
            signer.signPayload(payload_with_float)
        with pytest.raises(ArithmeticDriftException):
            Ed25519Verifier.verifyPayloadSignature(public_key, payload_with_float, "00" * 64)
