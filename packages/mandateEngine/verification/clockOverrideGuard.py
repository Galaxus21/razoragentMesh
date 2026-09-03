"""Bounds the client-supplied `serverTime` clock override on the settlement HTTP surface.

`serverTime` travels on the unsigned outer envelope of the settlement request -- outside all
three mandate signatures -- and the saga threads it into every expiry decision it makes:

    * mandate validity            verification/budgetGate.py
    * inventory-lock expiry       settlement/twoPhaseCommitSaga.py
    * the NTP drift window        nonce/nonceLedger.py
    * cumulative-spend expiry     verification/settlementLedger.py
    * the GSTR-1 invoice date     tax/gstrInvoiceEngine.py

Unbounded, it is a clock the caller owns. `serverTime=0` makes every expiry comparison pass, so
an expired delegation settles and a statutory tax invoice is back-dated, without breaking a
single signature. Only the MCP `execute_settlement` tool ever closed this, by setting the value
server-side and never exposing it as a tool input; the HTTP endpoint and both buyer SDKs passed
whatever the caller sent.

The bound lives here rather than on the Pydantic model so that `serverTime` stays usable as a
determinism seam by tests that drive the saga directly. What is closed is the HTTP surface --
the only part of this an attacker can reach.
"""

import time
from typing import Optional

from ..config import getMandateEngineSettings
from ..nonce.nonceLedger import maxNtpDriftToleranceSeconds, minNtpDriftToleranceSeconds


class ClockOverrideRejectedException(Exception):
    """Raised when a caller supplies a serverTime that is not near the real clock."""


def rejectOutOfWindowServerTime(serverTime: Optional[int]) -> None:
    """Refuses a clock override that sits outside the NTP drift window of the real clock.

    The window is the nonce ledger's own [T - 5s, T + 60s], imported rather than restated so the
    two cannot drift apart (rule V-03: one business rule, one implementation).

    Omitting `serverTime` is always allowed and means "use the server's own clock". The
    permissive mode is opt-in via ALLOW_CLIENT_SERVER_TIME and defaults to off, because a guard
    whose default is "allow" is not a guard.
    """
    if serverTime is None:
        return
    if getMandateEngineSettings().allowUnboundedClientServerTime:
        return

    realTime = int(time.time())
    earliest = realTime - minNtpDriftToleranceSeconds
    latest = realTime + maxNtpDriftToleranceSeconds
    if not earliest <= serverTime <= latest:
        raise ClockOverrideRejectedException(
            f"serverTime {serverTime} is outside the permitted drift window "
            f"[{earliest}, {latest}]. It overrides every expiry check in the settlement saga, "
            "so it may only be supplied close to the real clock. Omit it to use the server's own."
        )


__all__ = [
    "ClockOverrideRejectedException",
    "rejectOutOfWindowServerTime",
]
