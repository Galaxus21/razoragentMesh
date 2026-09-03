"""Coverage-gap tests for RFC 8785 JCS canonical byte production.

These bytes are what every Ed25519 signature in the protocol is computed over, so any
silent change to them makes signatures produced by two peers disagree even when both
believe they signed the same payload. Each test below kills a specific surviving mutant
in packages/mandateEngine/crypto/jcsCanonicalizer.py that the standing suite does not
notice.
"""

from razoragentMesh.packages.mandateEngine.crypto.jcsCanonicalizer import (
    canonicalizeJson,
)


def testNonAsciiIsEmittedAsRawUtf8NotEscaped() -> None:
    """Kills the L70 mutation ensure_ascii=False -> True.

    Indian merchant payloads carry rupee signs and Devanagari names. RFC 8785 mandates
    UTF-8 output, so the canonical bytes must contain the literal UTF-8 encoding of a
    non-ASCII character, never a backslash-u escape. If ensure_ascii flips to True the
    rupee sign becomes the six ASCII bytes '\\u20b9', changing the signed bytes for
    every payload with a non-ASCII character and breaking cross-peer signature match.
    """
    canonicalBytes = canonicalizeJson({"merchantName": "₹Store"})
    # Rupee sign U+20B9 as UTF-8 is exactly these three bytes.
    assert canonicalBytes == b'{"merchantName":"\xe2\x82\xb9Store"}'
    assert b"\xe2\x82\xb9" in canonicalBytes
    assert b"\\u20b9" not in canonicalBytes


def testAstralKeySortsBeforeHighBmpKeyByUtf16Rule() -> None:
    """Kills the L69 mutation sort_keys=False -> True (V-04 documented behaviour).

    _utf16SortKey deliberately orders keys by UTF-16 code unit. An astral-plane emoji
    U+1F600 encodes to the surrogate pair D83D DE00, whose leading unit D83D is below
    the high-BMP character U+FF00 (FF00) -- so the emoji must sort FIRST despite its
    larger code point. Passing sort_keys=True lets json.dumps re-sort by Python's
    code-point order, which would place U+FF00 first and flip the signed byte order.
    """
    canonicalBytes = canonicalizeJson({"＀": 1, "\U0001f600": 2})
    # Emoji (UTF-8 f0 9f 98 80) key must precede the U+FF00 (UTF-8 ef bc 80) key.
    assert canonicalBytes == b'{"\xf0\x9f\x98\x80":2,"\xef\xbc\x80":1}'
    emojiPos = canonicalBytes.index(b"\xf0\x9f\x98\x80")
    ff00Pos = canonicalBytes.index(b"\xef\xbc\x80")
    assert emojiPos < ff00Pos


def testSetNormalizesToSortedArrayNotNull() -> None:
    """Kills the L58 mutation return sorted([...]) -> return None.

    A set-valued field must canonicalize to a deterministic sorted JSON array so both
    signing peers agree on the bytes. If that branch returns None the field silently
    becomes null: signatures over the true membership would never be reproducible.
    Asserting the exact array bytes (not merely equality of two canonicalizations,
    which also holds when both are null) is what notices the mutation.
    """
    canonicalBytes = canonicalizeJson({"tags": {3, 1, 2}})
    assert canonicalBytes == b'{"tags":[1,2,3]}'
    assert b"null" not in canonicalBytes
