import {
  deliveryTierStandard,
  deliveryTierExpress,
  deliveryTierSameDay,
  courierDelhivery,
  courierBlueDart,
  zoneCodeA,
  zoneCodeB,
  zoneCodeC,
  zoneCodeD,
  zoneAStandardHours,
  zoneAStandardCostPaise,
  zoneAExpressHours,
  zoneAExpressCostPaise,
  zoneASameDayHours,
  zoneASameDayCostPaise,
  zoneBStandardHours,
  zoneBStandardCostPaise,
  zoneBExpressHours,
  zoneBExpressCostPaise,
  zoneCStandardHours,
  zoneCStandardCostPaise,
  zoneCExpressHours,
  zoneCExpressCostPaise,
  defaultFallbackState
} from "../constants/protocolConstants.js";
import { lookupStateFromPincode } from "./skuQuoter.js";
import {
  ShippingSlaRequest,
  ShippingSlaResponse,
  shippingSlaRequestSchema,
  shippingSlaResponseSchema
} from "../schemas/shippingSlaSchema.js";

export const cityPrefixLength = 3;
export const statePrefixLength = 2;
export const baseWeightGramsLimit = 500;
export const extraWeightChunkGrams = 500;
export const extraWeightSurchargePaise = 1000;

export function resolveZoneCode(originPincode: string, deliveryPincode: string): string {
  if (originPincode.slice(0, cityPrefixLength) === deliveryPincode.slice(0, cityPrefixLength)) {
    return zoneCodeA;
  }

  // One lookup for both sides, so the shipping path and the tax path agree on where a pincode is.
  // The origin is the mesh's own configured pincode, so defaultFallbackState is a real default
  // there; the delivery side has no such licence, and an unmapped prefix is now ZONE_D rather
  // than the raw prefix string -- which happened to sort as "not the origin state" and so read as
  // an ordinary out-of-state delivery the mesh could quote and ship.
  const originState = lookupStateFromPincode(originPincode) ?? defaultFallbackState;
  const deliveryState = lookupStateFromPincode(deliveryPincode);

  if (deliveryState === undefined) {
    // ZONE_D: the mesh does not know where this pincode is. The old code fell back to the raw
    // prefix string, which could never equal the origin state, so an unknown address quietly
    // priced as an ordinary out-of-state delivery.
    return zoneCodeD;
  }
  if (originState === deliveryState) {
    return zoneCodeB;
  }
  return zoneCodeC;
}

export function computeWeightSurcharge(packageWeightGrams: number): number {
  if (packageWeightGrams <= baseWeightGramsLimit) {
    return 0;
  }
  const excessGrams = packageWeightGrams - baseWeightGramsLimit;
  const extraChunks = Math.ceil(excessGrams / extraWeightChunkGrams);
  return extraChunks * extraWeightSurchargePaise;
}

export function normalizeShippingRequest(rawInput: unknown): ShippingSlaRequest {
  const inputObj = rawInput as Record<string, unknown>;
  const normalized = {
    origin_pincode: inputObj.origin_pincode ?? inputObj.originPincode,
    delivery_pincode: inputObj.delivery_pincode ?? inputObj.deliveryPincode,
    package_weight_grams: inputObj.package_weight_grams ?? inputObj.packageWeightGrams,
    required_delivery_tier: inputObj.required_delivery_tier ?? inputObj.requiredDeliveryTier ?? deliveryTierStandard
  };

  return shippingSlaRequestSchema.parse(normalized);
}

function resolveTierAndSla(
  zone: string,
  tier: string
): { slaHours: number; baseCostPaise: number; courier: string } {
  if (zone === zoneCodeA) {
    if (tier === deliveryTierSameDay) {
      return { slaHours: zoneASameDayHours, baseCostPaise: zoneASameDayCostPaise, courier: courierBlueDart };
    }
    if (tier === deliveryTierExpress) {
      return { slaHours: zoneAExpressHours, baseCostPaise: zoneAExpressCostPaise, courier: courierBlueDart };
    }
    return { slaHours: zoneAStandardHours, baseCostPaise: zoneAStandardCostPaise, courier: courierDelhivery };
  }

  if (zone === zoneCodeB) {
    if (tier === deliveryTierExpress || tier === deliveryTierSameDay) {
      return { slaHours: zoneBExpressHours, baseCostPaise: zoneBExpressCostPaise, courier: courierBlueDart };
    }
    return { slaHours: zoneBStandardHours, baseCostPaise: zoneBStandardCostPaise, courier: courierDelhivery };
  }

  if (tier === deliveryTierExpress || tier === deliveryTierSameDay) {
    return { slaHours: zoneCExpressHours, baseCostPaise: zoneCExpressCostPaise, courier: courierBlueDart };
  }
  return { slaHours: zoneCStandardHours, baseCostPaise: zoneCStandardCostPaise, courier: courierDelhivery };
}

/**
 * Which tiers a zone can actually honour. ZONE_D is the unknown-address zone and honours none:
 * the mandate engine refuses an unmapped pincode outright with InvalidPincodeException, so a
 * quote for one is a purchase that dies at settlement.
 */
export function availableTiersForZone(zone: string): string[] {
  if (zone === zoneCodeD) {
    return [];
  }
  if (zone === zoneCodeA) {
    return [deliveryTierStandard, deliveryTierExpress, deliveryTierSameDay];
  }
  // Zones B and C are reachable overnight at best; resolveTierAndSla already collapses a sameDay
  // request onto express pricing there, which promised a tier the network cannot meet.
  return [deliveryTierStandard, deliveryTierExpress];
}

export function verifyShippingSla(rawRequest: unknown): ShippingSlaResponse {
  const request = normalizeShippingRequest(rawRequest);
  const zone = resolveZoneCode(request.origin_pincode, request.delivery_pincode);
  const availableTiers = availableTiersForZone(zone);

  // serviceable was hardcoded true, so verify_shipping_sla answered "yes" for a pincode the
  // mandate engine would later refuse outright -- the agent was told the address was fine and
  // the purchase died at settlement. Report the negative answer instead of raising, following
  // oosHealingRoute's precedent for an expected no.
  if (availableTiers.length === 0) {
    return shippingSlaResponseSchema.parse({
      guaranteed_sla_hours: zoneCStandardHours,
      shipping_cost_paise: 0,
      courier_partner: courierDelhivery,
      zone_code: zone,
      serviceable: false,
      unserviceable_reason:
        `No courier serves delivery pincode ${request.delivery_pincode}: the prefix ` +
        `'${request.delivery_pincode.slice(0, statePrefixLength)}' is not in the mesh's ` +
        "serviceability map, and settlement would refuse it as an invalid pincode. Ask the " +
        "buyer for a different delivery address.",
      available_delivery_tiers: availableTiers
    });
  }

  if (!availableTiers.includes(request.required_delivery_tier)) {
    const { slaHours: bestHours, baseCostPaise: bestCost, courier: bestCourier } =
      resolveTierAndSla(zone, deliveryTierExpress);
    return shippingSlaResponseSchema.parse({
      guaranteed_sla_hours: bestHours,
      shipping_cost_paise: bestCost + computeWeightSurcharge(request.package_weight_grams),
      courier_partner: bestCourier,
      zone_code: zone,
      serviceable: false,
      unserviceable_reason:
        `${request.required_delivery_tier} delivery is not offered to ${zone}. The fastest ` +
        `available tier is express at ${bestHours} hours. Re-request with one of: ` +
        `${availableTiers.join(", ")}.`,
      available_delivery_tiers: availableTiers
    });
  }

  const { slaHours, baseCostPaise, courier } = resolveTierAndSla(
    zone,
    request.required_delivery_tier
  );
  const weightSurchargePaise = computeWeightSurcharge(request.package_weight_grams);
  const totalShippingCostPaise = baseCostPaise + weightSurchargePaise;

  const response: ShippingSlaResponse = {
    guaranteed_sla_hours: slaHours,
    shipping_cost_paise: totalShippingCostPaise,
    courier_partner: courier,
    zone_code: zone,
    serviceable: true,
    available_delivery_tiers: availableTiers
  };

  return shippingSlaResponseSchema.parse(response);
}
