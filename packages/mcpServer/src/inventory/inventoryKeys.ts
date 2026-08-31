// Redis key names for the inventory subsystem, in one place so the acquire path and the expiry
// sweeper cannot drift apart.
//
// Every key carries the same `{inventory}` hash tag. That is deliberate: the acquire and sweep
// scripts touch several of these keys in a single EVAL, which Redis Cluster only permits when
// they hash to the same slot.

export const stockKeyPrefix = "{inventory}:stock:";
export const lockKeyPrefix = "{inventory}:lock:";
export const globalFencingKey = "{inventory}:fencing:global";
export const activeReservationsKey = "{inventory}:reservations";
export const reservationQuantitiesKey = "{inventory}:reservationQty";

export const reservationEntrySeparator = "|";

// `<lockToken>|<skuId>` -- the sweeper parses the SKU back out to know which stock counter to
// credit, without a second round trip.
export function buildReservationEntry(lockToken: string, skuId: string): string {
  return `${lockToken}${reservationEntrySeparator}${skuId}`;
}
