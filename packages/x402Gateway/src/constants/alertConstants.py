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

# Callback URL SSRF Guard
requiredCallbackScheme: str = "https"
devModeCallbackScheme: str = "http"
devModeCallbackHost: str = "localhost"
# Dedicated opt-in flag (not the app-wide ENVIRONMENT var, whose own default is
# "development") so the HTTPS requirement stays on by default in every deployment,
# including this one, unless someone deliberately enables it for a local demo.
allowLocalhostCallbackEnvVar: str = "ALLOW_LOCALHOST_CALLBACK"

__all__ = [
    "allowLocalhostCallbackEnvVar",
    "defaultWebhookTimeoutSeconds",
    "devModeCallbackHost",
    "devModeCallbackScheme",
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
    "requiredCallbackScheme",
    "statusAlertActive",
    "statusAlertCancelled",
    "statusDispatchFailed",
    "statusDispatchSuccess",
]
