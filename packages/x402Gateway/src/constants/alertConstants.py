"""Constants for Gateway price-drop alert subscriptions and webhook dispatching."""

redisAlertPriceDropPrefix: str = "mesh:alerts:priceDrop:"
redisAlertLookupPrefix: str = "mesh:alerts:lookup:"

headerMeshSignature: str = "X-Mesh-Signature"
headerRazorpaySignature: str = "X-Razorpay-Signature"
headerMeshEvent: str = "X-Mesh-Event"
headerMeshDeliveryId: str = "X-Mesh-Delivery-Id"

eventPriceDropTriggered: str = "mesh.price_drop.triggered"
statusAlertActive: str = "active"
statusAlertCancelled: str = "cancelled"
statusDispatchSuccess: str = "dispatched"
statusDispatchFailed: str = "failed"

defaultWebhookTimeoutSeconds: float = 5.0
minTtlSeconds: int = 1
idPrefixAlert: str = "alert_"
idPrefixDelivery: str = "del_"
httpStatusOkMin: int = 200
httpStatusOkMax: int = 300

__all__ = [
    "defaultWebhookTimeoutSeconds",
    "eventPriceDropTriggered",
    "headerMeshDeliveryId",
    "headerMeshEvent",
    "headerMeshSignature",
    "headerRazorpaySignature",
    "httpStatusOkMax",
    "httpStatusOkMin",
    "idPrefixAlert",
    "idPrefixDelivery",
    "minTtlSeconds",
    "redisAlertLookupPrefix",
    "redisAlertPriceDropPrefix",
    "statusAlertActive",
    "statusAlertCancelled",
    "statusDispatchFailed",
    "statusDispatchSuccess",
]
