"""Move a SKU's promotion window relative to now, so Smart Wait has something to point at.

`upcoming_promotions` only carries a campaign whose window has not opened yet. A window authored
for a demo goes stale the moment the demo runs late: the sale opens, the field empties, and the
Smart Wait story silently stops being demonstrable. That is exactly what happened on 2026-09-03 --
`SKU-TEST-MON-SALE` was authored to open at 21:11, the buyer runs began after that, and every
agent that quoted it received an empty `upcoming_promotions`.

Re-publishes the listing through the same proxy the Studio's "Publish to Mesh" button posts to,
changing nothing but the promotion timestamps.

  python scripts/reauthorSaleWindow.py                      # opens in 45 min (Smart Wait)
  python scripts/reauthorSaleWindow.py --lead-minutes -5    # already open (priced-discount demo)
  python scripts/reauthorSaleWindow.py --sku SKU-OTHER-01

usage: python scripts/reauthorSaleWindow.py [--sku ID] [--lead-minutes N] [--hours N]
"""

import argparse
import json
import os
import sys
import time
import urllib.request
from typing import Any, Dict

# Constants
defaultDashboardUrl = "http://localhost:3000"
defaultMerchantApiUrl = "http://localhost:4002"
catalogProxyPath = "/api/mesh/catalog"
requestTimeoutSeconds = 15

exitCodeSucceeded = 0
exitCodeFailed = 1

# Must match `seedMerchantDid` in seedCatalog.py -- see demoNegotiationPolicy.py.
demoMerchantDid = "did:mesh:merchant_razoragent_demo_01"
defaultSkuId = "SKU-TEST-MON-SALE"

# Far enough ahead that a quote taken during the demo still shows the sale as upcoming, close
# enough that "worth waiting for?" is a real question rather than an obvious no.
defaultLeadMinutes = 45
defaultDurationHours = 24
secondsPerMinute = 60
secondsPerHour = 3600


def _serviceUrl(variableName: str, fallback: str) -> str:
    return os.environ.get(variableName, fallback).rstrip("/")


def _readListing(skuId: str) -> Dict[str, Any]:
    url = "%s/api/v1/merchant/%s/catalog/%s" % (
        _serviceUrl("MERCHANT_API_URL", defaultMerchantApiUrl), demoMerchantDid, skuId)
    with urllib.request.urlopen(url, timeout=requestTimeoutSeconds) as response:
        return json.loads(response.read().decode())


def _publishListing(listing: Dict[str, Any]) -> int:
    request = urllib.request.Request(
        _serviceUrl("DASHBOARD_URL", defaultDashboardUrl) + catalogProxyPath,
        data=json.dumps(listing).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=requestTimeoutSeconds) as response:
        return response.status


def _shiftPromotions(listing: Dict[str, Any], startsAt: int, endsAt: int) -> int:
    promotions = listing.get("promotions") or []
    for promotion in promotions:
        promotion["startsAtUnix"] = startsAt
        promotion["endsAtUnix"] = endsAt
    return len(promotions)


def _parseArguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sku", default=defaultSkuId)
    parser.add_argument("--lead-minutes", type=int, default=defaultLeadMinutes,
                        help="minutes until the sale opens; negative opens it in the past")
    parser.add_argument("--hours", type=int, default=defaultDurationHours,
                        help="how long the sale stays open")
    return parser.parse_args()


def main() -> int:
    arguments = _parseArguments()
    try:
        listing = _readListing(arguments.sku)
    except Exception as error:  # noqa: BLE001 - an ops script reports, it does not re-raise
        print("could not read %s: %s" % (arguments.sku, error), file=sys.stderr)
        return exitCodeFailed

    now = int(time.time())
    startsAt = now + arguments.lead_minutes * secondsPerMinute
    endsAt = startsAt + arguments.hours * secondsPerHour
    shifted = _shiftPromotions(listing, startsAt, endsAt)
    if shifted == 0:
        print("%s carries no promotions; nothing to move" % arguments.sku, file=sys.stderr)
        return exitCodeFailed

    try:
        status = _publishListing(listing)
    except Exception as error:  # noqa: BLE001
        print("publish failed: %s" % error, file=sys.stderr)
        return exitCodeFailed

    state = "already open" if startsAt <= now else "opens in %d min" % arguments.lead_minutes
    print("publish HTTP %s -- %d promotion(s) on %s, %s" %
          (status, shifted, arguments.sku, state))
    print("window: starts=%d ends=%d" % (startsAt, endsAt))
    return exitCodeSucceeded


if __name__ == "__main__":
    sys.exit(main())
