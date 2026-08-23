"""Merchant API routes subpackage."""

from .bulkIngestRoute import (
    bulkIngestRouter,
    erpBatchSync,
    ingestCsvBulk,
    shopifyWebhookSync,
)
from .catalogRoute import (
    catalogRouter,
    createSku,
    deleteSku,
    getSku,
    updateSku,
)
from .dependencies import (
    getRedisClient,
)
from .policyRoute import (
    getPolicy,
    policyRouter,
    setPolicy,
)
from .registrationRoute import (
    registerMerchant,
    registrationRouter,
)

__all__ = [
    "bulkIngestRouter",
    "catalogRouter",
    "createSku",
    "deleteSku",
    "erpBatchSync",
    "getPolicy",
    "getRedisClient",
    "getSku",
    "ingestCsvBulk",
    "policyRouter",
    "registerMerchant",
    "registrationRouter",
    "setPolicy",
    "shopifyWebhookSync",
    "updateSku",
]
