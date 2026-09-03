"""Read or flip the demo merchant's negotiation opt-in, through the Studio's own proxy.

Two jobs, both demo-facing:

  * B-14 needs `negotiate_price` to answer DECLINED for real. That means the merchant's stored
    consent has to actually be off. It cannot be faked by passing a different `merchantDid` --
    the x402 gateway ignores the caller's claim and names the merchant from the SKU's listing.
  * After that scenario runs, negotiation is left off, and every later bid is declined. A
    rehearsal on 2026-09-03 lost its whole negotiation story that way and nobody noticed until
    the transcripts were read. `demoNegotiationPolicy.py on` is the two-second undo.

Writes go through the dashboard proxy rather than straight to the merchant API, because that is
the hop the Negotiation Policy panel makes: exercising it here means a green run also proves the
path the demo clicks through.

Only `negotiationEnabled` is changed. The margin floor and turn cap are read back from the stored
policy and rewritten as they were, so flipping the switch cannot silently reset a merchant who has
tuned them -- `seedCatalog.py` sets the seeded values and this script is not a second opinion on
what they should be.

usage: python scripts/demoNegotiationPolicy.py [show|on|off]
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict

# Constants
defaultDashboardUrl = "http://localhost:3000"
policyProxyPath = "/api/mesh/policy"
requestTimeoutSeconds = 15

exitCodeSucceeded = 0
exitCodeFailed = 1

# The merchant the whole demo catalog is published under. Must match `seedMerchantDid` in
# seedCatalog.py: the gateway resolves a SKU's owning merchant from its listing, so a policy
# saved against any other DID governs nothing.
demoMerchantDid = "did:mesh:merchant_razoragent_demo_01"

# Used only when no policy has ever been stored for this merchant, which is the state a fresh
# `docker compose up` leaves behind if the catalog seeder has not run. Mirrors the seeded policy.
seededPolicyDefaults: Dict[str, Any] = {
    "marginFloorBps": 1200,
    "minimumOrderQuantity": 1,
    "autoAcceptSpreadPaise": 0,
    "maxNegotiationTurns": 5,
}


def _dashboardUrl() -> str:
    return os.environ.get("DASHBOARD_URL", defaultDashboardUrl).rstrip("/")


def _readPolicy() -> Dict[str, Any]:
    """Returns the stored policy, or the seeded defaults if this merchant has never saved one.

    A 404 here is not an error: it is the default state of every merchant, and the Studio panel
    renders it as "not enabled" rather than as a failure.
    """
    url = "%s%s?merchantDid=%s" % (_dashboardUrl(), policyProxyPath, demoMerchantDid)
    try:
        with urllib.request.urlopen(url, timeout=requestTimeoutSeconds) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
        stored = dict(seededPolicyDefaults)
        stored["merchantDid"] = demoMerchantDid
        stored["negotiationEnabled"] = False
        stored["createdAtTimestamp"] = 0
        return stored


def _writePolicy(policy: Dict[str, Any]) -> None:
    request = urllib.request.Request(
        _dashboardUrl() + policyProxyPath,
        data=json.dumps(policy).encode(),
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    with urllib.request.urlopen(request, timeout=requestTimeoutSeconds) as response:
        print("PUT %s -> HTTP %s" % (policyProxyPath, response.status))
        print(response.read().decode()[:300])


def showPolicy() -> None:
    policy = _readPolicy()
    state = "ON" if policy.get("negotiationEnabled") else "OFF"
    print("negotiation is %s for %s" % (state, demoMerchantDid))
    print(json.dumps(policy, indent=2))


def setPolicy(enabled: bool) -> None:
    """Flips `negotiationEnabled` and rewrites every other field exactly as it was stored."""
    policy = _readPolicy()
    policy["merchantDid"] = demoMerchantDid
    policy["negotiationEnabled"] = enabled
    now = int(time.time())
    # The merchant-api model is extra="forbid" and requires both timestamps; omitting either is
    # a 422 that names the field.
    policy["createdAtTimestamp"] = policy.get("createdAtTimestamp") or now
    policy["updatedAtTimestamp"] = now
    _writePolicy(policy)


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else "show"
    actions = {"show": showPolicy, "on": lambda: setPolicy(True), "off": lambda: setPolicy(False)}
    if command not in actions:
        print("usage: python scripts/demoNegotiationPolicy.py [show|on|off]", file=sys.stderr)
        return exitCodeFailed
    try:
        actions[command]()
    except Exception as error:  # noqa: BLE001 - an ops script reports, it does not re-raise
        print("failed: %s" % error, file=sys.stderr)
        return exitCodeFailed
    return exitCodeSucceeded


if __name__ == "__main__":
    sys.exit(main())
