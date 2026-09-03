"""Watches the catalog broadcast and fires the price-drop alerts nothing else ever fired.

Why this exists: registering an alert returned 201 with status "active", and then nothing --
`dispatchPriceDropAlerts` had no production caller anywhere in the repo, only tests. An agent
could subscribe to a price it wanted and would never hear about it, which is worse than having
no endpoint at all, because the 201 says otherwise.

The price change happens in merchantApi and the alerts live here, so the two are in different
processes. Rather than couple them with an HTTP call, this subscribes to `mesh:catalog:updates`
-- the same Redis pub/sub channel merchantApi already publishes every upsert to and the MCP
server already consumes to keep its catalog live. No new contract, and the gateway already
holds a Redis connection for merchant policy lookups.
"""

import asyncio
import json
import logging
from typing import Any, Dict, Optional

from .priceDropAlertManager import PriceDropAlertManager

logger = logging.getLogger(__name__)

redisCatalogUpdatesChannel: str = "mesh:catalog:updates"

# The actions that carry an `item`, and so a price. A removal carries only a skuId: there is no
# new price to compare a target against, and treating a delisting as a drop to zero would fire
# every alert on the SKU at once.
#
# Both spellings, matching what the MCP server's own subscriber accepts
# (mcpServer/src/catalog/catalogStore.ts): merchantApi publishes CATALOG_ITEM_*, while the
# dashboard's seeder and the older fixtures use the bare forms. A subscriber that knew only one
# would sit silent against the other producer and look like a dead feature rather than a mismatch.
catalogActionsWithPrice = frozenset(
    {"CATALOG_ITEM_ADDED", "CATALOG_ITEM_UPDATED", "ADDED", "UPDATED"}
)

# Redis delivers `None` between messages when nothing arrived within the timeout. Bounded rather
# than blocking forever so the loop observes cancellation promptly at shutdown.
subscriberPollTimeoutSeconds: float = 1.0


def extractPriceFromCatalogEvent(rawMessage: Any) -> Optional[Dict[str, Any]]:
    """Pulls (skuId, price) out of a catalog event, or None when the event carries no price.

    Tolerant by design: this consumes a broadcast it does not own, and a malformed or unfamiliar
    event must be skipped rather than allowed to kill the subscriber loop and silently stop every
    future alert.
    """
    try:
        payload = json.loads(rawMessage) if isinstance(rawMessage, (str, bytes)) else rawMessage
    except (ValueError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None

    action = payload.get("action") or payload.get("actionType") or payload.get("event")
    if action not in catalogActionsWithPrice:
        return None

    item = payload.get("item")
    if not isinstance(item, dict):
        return None

    skuId = item.get("skuId") or payload.get("skuId")
    pricePaise = item.get("baseUnitPricePaise")
    if not isinstance(skuId, str) or not skuId:
        return None
    if not isinstance(pricePaise, int) or isinstance(pricePaise, bool) or pricePaise < 0:
        return None
    return {"skuId": skuId, "pricePaise": pricePaise}


class CatalogPriceWatcher:
    """Subscribes to catalog updates and dispatches matching price-drop alerts."""

    def __init__(
        self,
        alertManager: PriceDropAlertManager,
        redisClient: Any,
    ) -> None:
        self._alertManager = alertManager
        self._redisClient = redisClient
        self._task: Optional[asyncio.Task] = None

    async def handleCatalogMessage(self, rawMessage: Any) -> int:
        """Dispatches alerts for one catalog event. Returns how many webhooks were sent."""
        change = extractPriceFromCatalogEvent(rawMessage)
        if change is None:
            return 0
        # The manager itself decides which alerts match: an alert fires when its target price is
        # at or above the new price, so a raise dispatches nothing and needs no special case here.
        results = await self._alertManager.dispatchPriceDropAlerts(
            change["skuId"], change["pricePaise"]
        )
        if results:
            logger.info(
                "Price-drop alerts dispatched for %s at %s paise: %s webhook(s)",
                change["skuId"],
                change["pricePaise"],
                len(results),
            )
        return len(results)

    async def runSubscriberLoop(self) -> None:
        """Consumes the catalog channel until cancelled."""
        pubsub = self._redisClient.pubsub()
        await pubsub.subscribe(redisCatalogUpdatesChannel)
        try:
            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=subscriberPollTimeoutSeconds
                )
                if message is None:
                    continue
                try:
                    await self.handleCatalogMessage(message.get("data"))
                except Exception as err:
                    # One bad event, or one unreachable callback URL, must not end the loop and
                    # take every future alert down with it.
                    logger.warning("Price-drop dispatch failed for a catalog event: %s", err)
        except asyncio.CancelledError:
            raise
        finally:
            try:
                await pubsub.unsubscribe(redisCatalogUpdatesChannel)
                await pubsub.close()
            except Exception:
                # Shutdown path: a Redis already gone cannot be unsubscribed from, and saying so
                # would be noise in the one log line an operator reads on a clean stop.
                pass

    def start(self) -> None:
        """Launches the subscriber as a background task."""
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self.runSubscriberLoop())

    async def stop(self) -> None:
        """Cancels the subscriber and waits for it to unwind."""
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None


__all__ = [
    "CatalogPriceWatcher",
    "catalogActionsWithPrice",
    "extractPriceFromCatalogEvent",
    "redisCatalogUpdatesChannel",
]
