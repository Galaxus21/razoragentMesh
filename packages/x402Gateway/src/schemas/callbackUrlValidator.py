"""SSRF guard for merchant-facing webhook callback URLs."""

import ipaddress
from urllib.parse import urlparse

from ..constants.alertConstants import devModeCallbackHost, devModeCallbackScheme, requiredCallbackScheme
from ..gatewayExceptions import UnsafeCallbackUrlException

__all__ = ["validateCallbackUrl"]

# Symbolic hostnames that always resolve (or are conventionally routed) to a
# non-public address, so they are blocked without a DNS lookup.
_unsafeHostnameDenylist: frozenset = frozenset({devModeCallbackHost, "metadata.google.internal"})


def _isUnsafeIpLiteral(hostname: str) -> bool:
    """Returns True if the hostname is itself a private, loopback, link-local,
    or reserved IP address literal (e.g. the 169.254.169.254 cloud metadata endpoint)."""
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return False
    return address.is_private or address.is_loopback or address.is_link_local or address.is_reserved


def validateCallbackUrl(candidateUrl: str, *, allowLocalhostCallback: bool = False) -> str:
    """Rejects callback URLs that are not plain HTTPS, or whose host is a known-unsafe
    symbolic name or a private/loopback/link-local/reserved IP literal.

    Deliberately syntactic only -- it never resolves the hostname via DNS. A validator
    that made a network call would be slow and environment-dependent (breaking in
    sandboxes with no DNS, and passing or failing differently across environments for
    the same input), and would not close the SSRF gap anyway: a resolution done here
    can differ from the one the HTTP client uses moments later (DNS rebinding), so it
    is not a substitute for validating the request at the point of dispatch.

    An HTTP URL to `devModeCallbackHost` is allowed only when the caller opts in with
    `allowLocalhostCallback=True`, which defaults to off so the HTTPS requirement stays
    on in every deployment unless someone deliberately relaxes it for a local demo.
    """
    parsed = urlparse(candidateUrl)
    hostname = (parsed.hostname or "").lower()

    isDevLoopback = (
        allowLocalhostCallback
        and parsed.scheme == devModeCallbackScheme
        and hostname == devModeCallbackHost
    )
    if isDevLoopback:
        return candidateUrl

    if parsed.scheme != requiredCallbackScheme or not hostname:
        raise UnsafeCallbackUrlException(
            f"callbackUrl must be a {requiredCallbackScheme} URL with an explicit host, got: {candidateUrl!r}"
        )
    if hostname in _unsafeHostnameDenylist or _isUnsafeIpLiteral(hostname):
        raise UnsafeCallbackUrlException(f"callbackUrl host '{hostname}' is not a permitted public address")
    return candidateUrl
