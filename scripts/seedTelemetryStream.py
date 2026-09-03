#!/usr/bin/env python3
"""Standalone Telemetry Stream Seeder for RazorAgent Mesh Dashboard.

Streams SCRIPTED, PRE-WRITTEN telemetry events into the Mandate Engine SSE broadcaster so the
dashboard can be demonstrated without Docker or a running mesh. Nothing here is the product of
an actual protocol execution: the hashes, signatures and prices below are fixtures.

Every event is therefore stamped provenance=SYNTHETIC, which the dashboard reads to label the
stream REPLAY instead of LIVE. Do not remove that stamp -- a seeded run that renders as live is
the exact dishonesty this flag exists to prevent. For real events, run a scenario from
/playground, which stamps provenance=LIVE.

Usage:
    python scripts/seedTelemetryStream.py --scenario all --delay-ms 350
    python scripts/seedTelemetryStream.py --scenario negotiation --delay-ms 200
    python scripts/seedTelemetryStream.py --scenario healing --delay-ms 250
    python scripts/seedTelemetryStream.py --scenario settlement --repeat 3
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List


def configureConsoleEncoding() -> None:
    """Forces UTF-8 output so the banner does not abort the run on a legacy console.

    A default Windows console uses cp1252, which cannot encode the emoji in the progress
    output: the script died with UnicodeEncodeError before sending a single event. The seeder
    is meant to be the no-Docker demo path, so it must run on the machine that needs it.
    """
    for consoleStream in (sys.stdout, sys.stderr):
        reconfigure = getattr(consoleStream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


configureConsoleEncoding()

defaultTelemetryEndpoint: str = "http://localhost:8000/api/v1/telemetry/events"
defaultDelayMilliseconds: int = 400
defaultRepeatCount: int = 1
defaultTimeoutSeconds: float = 5.0
httpSuccessStatusCode: int = 200
syntheticProvenanceValue: str = "SYNTHETIC"
provenanceFieldName: str = "provenance"
# The previous default asserted liveness in the identifier itself and then showed up verbatim
# in the dashboard's session column, so a fixture session read as an agent session.
defaultSessionIdPrefix: str = "session_seeded_fixture"


def buildPowEvent(sessionId: str, nowMs: int) -> Dict[str, Any]:
    """Builds a PoW Challenge Solved telemetry event."""
    return {
        "eventId": f"evt-pow-{nowMs}",
        "eventType": "POW_CHALLENGE_SOLVED",
        "timestampMs": nowMs,
        "sessionId": sessionId,
        "payload": {
            "challenge": "a9f8b7c6d5e4f3a2",
            "nonce": 48921,
            "hash": "0000a7b8c9d0e1f2456789abcdef0123456789abcdef0123456789abcdef0123",
            "solveDurationMs": 14,
            "leadingZeros": 4,
        },
    }


def buildMcpQuoteEvents(sessionId: str, nowMs: int) -> List[Dict[str, Any]]:
    """Builds MCP Tool Call and Result telemetry events."""
    return [
        {
            "eventId": f"evt-mcp-call-{nowMs}",
            "eventType": "MCP_TOOL_CALL",
            "timestampMs": nowMs,
            "sessionId": sessionId,
            "payload": {
                "toolName": "get_live_sku_quote",
                "callId": "call-quote-001",
                "callerAgentId": "did:razoragent:buyer:procurement-bot-01",
                "parameters": {
                    "sku_id": "SKU-IND-SENSOR-001",
                    "quantity": 10,
                    "delivery_pincode": "560001",
                },
            },
        },
        {
            "eventId": f"evt-mcp-res-{nowMs + 45}",
            "eventType": "MCP_TOOL_RESULT",
            "timestampMs": nowMs + 45,
            "sessionId": sessionId,
            "payload": {
                "toolName": "get_live_sku_quote",
                "callId": "call-quote-001",
                "success": True,
                "result": {
                    "base_unit_price_paise": 420000,
                    "offered_unit_price_paise": 420000,
                    "gst_rate_percent": 18,
                    "hsn_code": "84713010",
                },
                "durationMs": 45,
            },
        },
    ]


def buildInventoryLockEvent(sessionId: str, nowMs: int) -> Dict[str, Any]:
    """Builds an Inventory Locked telemetry event."""
    return {
        "eventId": f"evt-inv-lock-{nowMs}",
        "eventType": "INVENTORY_LOCKED",
        "timestampMs": nowMs,
        "sessionId": sessionId,
        "payload": {
            "skuId": "SKU-IND-SENSOR-001",
            "quantityLocked": 10,
            "lockToken": "lock-f782-990a-11bc-44da",
            "fencingToken": 1042,
            "ttlSeconds": 60,
        },
    }


def buildMandateEvents(sessionId: str, nowMs: int) -> List[Dict[str, Any]]:
    """Builds AP2 Intent and Execution Mandate Signed telemetry events."""
    return [
        {
            "eventId": f"evt-mandate-intent-{nowMs}",
            "eventType": "MANDATE_SIGNED",
            "timestampMs": nowMs,
            "sessionId": sessionId,
            "payload": {
                "mandateType": "INTENT",
                "mandateHash": "0x89ab45cd67ef123489ab45cd67ef123489ab45cd67ef123489ab45cd67ef1234",
                "signerKeyDid": "did:razoragent:cfo:corporate-treasury-01",
                "signatureHex": "ed25519_sig_intent_9876543210abcdef9876543210abcdef9876543210abcdef",
                "maxBudgetPaise": 5000000,
                "verificationStatus": "VALID",
                "canonicalJcsPreview": '{"budgetPaise":5000000,"category":"industrial_electronics"}',
            },
        },
        {
            "eventId": f"evt-mandate-exec-{nowMs + 60}",
            "eventType": "MANDATE_SIGNED",
            "timestampMs": nowMs + 60,
            "sessionId": sessionId,
            "payload": {
                "mandateType": "EXECUTION",
                "mandateHash": "0x77bb88cc99dd00ee11ff22aa33bb44cc55dd66ee77ff88aa99bb00cc11dd22ee",
                "signerKeyDid": "did:razoragent:buyer:procurement-bot-01",
                "signatureHex": "ed25519_sig_exec_1234567890abcdef1234567890abcdef1234567890abcdef",
                "boundChainHash": "0x89ab45cd67ef123489ab45cd67ef123489ab45cd67ef123489ab45cd67ef1234",
                "totalAmountPaise": 4200000,
                "verificationStatus": "VALID",
                "canonicalJcsPreview": '{"boundChainHash":"0x89ab...","totalAmountPaise":4200000}',
            },
        },
    ]


def buildNegotiationTurnsEvents(sessionId: str, nowMs: int) -> List[Dict[str, Any]]:
    """Builds multi-turn B2B algorithmic price negotiation events."""
    return [
        {
            "eventId": f"evt-bid-turn-1-{nowMs}",
            "eventType": "BID_TURN_COMPLETED",
            "timestampMs": nowMs,
            "sessionId": sessionId,
            "payload": {
                "turnNumber": 1,
                "maxTurns": 5,
                "buyerBidPaise": 3300000,
                "sellerAskPaise": 3600000,
                "spreadPaise": 300000,
                "microFeePaidPaise": 50,
                "cumulativeMicroFeesPaise": 50,
                "status": "IN_PROGRESS",
            },
        },
        {
            "eventId": f"evt-bid-turn-2-{nowMs + 80}",
            "eventType": "BID_TURN_COMPLETED",
            "timestampMs": nowMs + 80,
            "sessionId": sessionId,
            "payload": {
                "turnNumber": 2,
                "maxTurns": 5,
                "buyerBidPaise": 3325000,
                "sellerAskPaise": 3450000,
                "spreadPaise": 125000,
                "microFeePaidPaise": 50,
                "cumulativeMicroFeesPaise": 100,
                "status": "IN_PROGRESS",
            },
        },
        {
            "eventId": f"evt-bid-turn-3-{nowMs + 160}",
            "eventType": "BID_TURN_COMPLETED",
            "timestampMs": nowMs + 160,
            "sessionId": sessionId,
            "payload": {
                "turnNumber": 3,
                "maxTurns": 5,
                "buyerBidPaise": 3350000,
                "sellerAskPaise": 3350000,
                "spreadPaise": 0,
                "microFeePaidPaise": 50,
                "cumulativeMicroFeesPaise": 150,
                "status": "CONVERGED",
            },
        },
        {
            "eventId": f"evt-neg-conv-{nowMs + 240}",
            "eventType": "NEGOTIATION_CONVERGED",
            "timestampMs": nowMs + 240,
            "sessionId": sessionId,
            "payload": {
                "finalAgreedUnitPricePaise": 3350000,
                "totalTurns": 3,
                "totalGrossPaise": 33500000,
                "contractAstHash": "0xcc99aa1188bb33dd44ee55ff66aa77bb88cc99dd00ee11ff22aa33bb44cc55dd",
            },
        },
    ]


def buildOosHealingEvent(sessionId: str, nowMs: int) -> Dict[str, Any]:
    """Builds Qdrant ANN vector self-healing and AST audit telemetry event."""
    return {
        "eventId": f"evt-oos-heal-{nowMs}",
        "eventType": "OOS_HEALED",
        "timestampMs": nowMs,
        "sessionId": sessionId,
        "payload": {
            "originalSkuId": "SKU-IND-SENSOR-001",
            "substituteSkuId": "SKU-IND-SENSOR-002-PLUS",
            "cosineSimilarity": 0.942,
            "originalPricePaise": 4200000,
            "substitutePricePaise": 4250000,
            "priceDeltaPaise": 50000,
            # Scripted, like every other number in this file, and stamped SYNTHETIC on the way
            # out. It is called out because this one used to be read as a measurement: it was
            # the ONLY producer of OOS_HEALED telemetry in the repository, so the dashboard's
            # "Sub-300ms Vector Self-Healing" tile displayed 214ms whatever the healer did.
            # The measured figure now comes from POST /api/v1/catalog/heal-oos, which times
            # OosInterceptor.findSubstitute, and metricsBar.tsx excludes SYNTHETIC events from
            # that average.
            "healingDurationMs": 214,
            "patchedMandateHash": "0x12fe89ab34cd56ef78ab90cd12ef34ab56cd78ef90ab12cd34ef56ab78cd90ef",
            "negativeConstraintsPassed": True,
        },
    }


def buildPaymentCapturedEvent(sessionId: str, nowMs: int) -> Dict[str, Any]:
    """Builds Razorpay 2PC settlement and multi-party split transfer event."""
    return {
        "eventId": f"evt-pay-captured-{nowMs}",
        "eventType": "PAYMENT_CAPTURED",
        "timestampMs": nowMs,
        "sessionId": sessionId,
        "payload": {
            "paymentId": "pay_A2A_Live_982341",
            "orderId": "order_Mesh_881290",
            "amountPaise": 4200000,
            "currency": "INR",
            "status": "captured",
            "transfers": [
                {
                    "transferId": "trf_merchant_001",
                    "recipientAccountId": "acc_merchant_nexus_01",
                    "amountPaise": 3800000,
                    "feePaise": 0,
                },
                {
                    "transferId": "trf_platform_002",
                    "recipientAccountId": "acc_razoragent_protocol",
                    "amountPaise": 20000,
                    "feePaise": 0,
                },
                {
                    "transferId": "trf_logistics_003",
                    "recipientAccountId": "acc_delhivery_direct",
                    "amountPaise": 380000,
                    "feePaise": 0,
                },
            ],
            "gstrInvoiceHash": "0xfa9812bc67de45fe9812bc67de45fe9812bc67de45fe9812bc67de45fe9812bc",
            "cgstPaise": 320340,
            "sgstPaise": 320340,
        },
    }


def buildRollbackEvent(sessionId: str, nowMs: int) -> Dict[str, Any]:
    """Builds a Route 2PC rollback event."""
    return {
        "eventId": f"evt-rollback-{nowMs}",
        "eventType": "ROUTE_ROLLBACK_TRIGGERED",
        "timestampMs": nowMs,
        "sessionId": sessionId,
        "payload": {
            "paymentId": "pay_A2A_Live_982341",
            "failureReason": "Fencing token expired before 2PC commit phase",
            "reversedTransfersCount": 3,
            "totalReversedPaise": 4200000,
        },
    }


def assembleScenarioEvents(scenario: str, sessionId: str) -> List[Dict[str, Any]]:
    """Assembles sequential event list for the specified scenario."""
    nowMs = int(time.time() * 1000)
    events: List[Dict[str, Any]] = []

    if scenario in ("all", "settlement"):
        events.append(buildPowEvent(sessionId, nowMs))
        events.extend(buildMcpQuoteEvents(sessionId, nowMs + 100))
        events.append(buildInventoryLockEvent(sessionId, nowMs + 200))
        events.extend(buildMandateEvents(sessionId, nowMs + 300))

    if scenario in ("all", "negotiation"):
        events.extend(buildNegotiationTurnsEvents(sessionId, nowMs + 500))

    if scenario in ("all", "healing"):
        events.append(buildOosHealingEvent(sessionId, nowMs + 800))

    if scenario in ("all", "settlement"):
        events.append(buildPaymentCapturedEvent(sessionId, nowMs + 1000))
    elif scenario == "rollback":
        events.append(buildInventoryLockEvent(sessionId, nowMs))
        events.append(buildRollbackEvent(sessionId, nowMs + 200))

    # Stamped here rather than inside each builder so a future scenario cannot be added without
    # it: everything this script emits is a fixture, without exception.
    for event in events:
        event[provenanceFieldName] = syntheticProvenanceValue

    return events


def dispatchTelemetryEvent(endpointUrl: str, event: Dict[str, Any]) -> bool:
    """Dispatches a single telemetry event frame to the Mandate Engine HTTP endpoint."""
    encodedData = json.dumps(event).encode("utf-8")
    request = urllib.request.Request(
        endpointUrl,
        data=encodedData,
        headers={"Content-Type": "application/json", "User-Agent": "RazorAgent-Seeder/2.0"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=defaultTimeoutSeconds) as response:
            return response.status in (httpSuccessStatusCode, 201)
    except urllib.error.URLError as networkError:
        print(f"  [DISPATCH ERROR] Failed to send {event['eventType']}: {networkError}")
        return False


def runSeederLoop(args: argparse.Namespace) -> None:
    """Executes the telemetry seeding loop."""
    print(f"🚀 RazorAgent Mesh Telemetry Seeder")
    print(f"   Mode:     REPLAY (scripted fixtures, provenance={syntheticProvenanceValue})")
    print(f"   Target:   {args.url}")
    print(f"   Scenario: {args.scenario}")
    print(f"   Delay:    {args.delay_ms} ms")
    print(f"   Repeat:   {args.repeat} cycle(s)\n")

    for cycleIndex in range(1, args.repeat + 1):
        sessionId = f"{args.session_id}_{cycleIndex}_{int(time.time())}"
        events = assembleScenarioEvents(args.scenario, sessionId)
        print(f"📦 [Cycle {cycleIndex}/{args.repeat}] Broadcasting {len(events)} events (Session: {sessionId})...")

        for eventIndex, event in enumerate(events, start=1):
            success = dispatchTelemetryEvent(args.url, event)
            statusMark = "✓" if success else "✗"
            print(f"   [{statusMark}] ({eventIndex}/{len(events)}) {event['eventType']} -> {event['eventId']}")
            if eventIndex < len(events):
                time.sleep(args.delay_ms / 1000.0)

        print(f"✨ Cycle {cycleIndex} complete.\n")


def parseCommandLineArguments() -> argparse.Namespace:
    """Configures and parses CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Broadcast authentic telemetry event streams into RazorAgent Mesh Dashboard."
    )
    parser.add_argument(
        "--url",
        default=defaultTelemetryEndpoint,
        help=f"Mandate Engine telemetry endpoint (default: {defaultTelemetryEndpoint})",
    )
    parser.add_argument(
        "--scenario",
        choices=["all", "settlement", "negotiation", "healing", "rollback"],
        default="all",
        help="Telemetry scenario type to simulate (default: all)",
    )
    parser.add_argument(
        "--delay-ms",
        type=int,
        default=defaultDelayMilliseconds,
        dest="delay_ms",
        help=f"Delay between sequential events in milliseconds (default: {defaultDelayMilliseconds})",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=defaultRepeatCount,
        help=f"Number of times to repeat the scenario (default: {defaultRepeatCount})",
    )
    parser.add_argument(
        "--session-id",
        default=defaultSessionIdPrefix,
        dest="session_id",
        help="Session identifier prefix",
    )
    return parser.parse_args()


if __name__ == "__main__":
    cliArgs = parseCommandLineArguments()
    runSeederLoop(cliArgs)
