"""JCS Canonicalization and SHA-256 digest serialization wrapper for gateway compiler.

Delegates directly to the canonical JCS Canonicalizer in mandateEngine, so the AST
contract compiler can never compute a different canonical form or hash than the
settlement engine that later verifies mandates signed over the same kind of payload.
"""

try:
    from razoragentMesh.packages.mandateEngine.crypto.jcsCanonicalizer import (
        canonicalizeJson,
        computeSha256Digest,
    )
except ImportError:
    from packages.mandateEngine.crypto.jcsCanonicalizer import (
        canonicalizeJson,
        computeSha256Digest,
    )

__all__ = [
    "canonicalizeJson",
    "computeSha256Digest",
]
