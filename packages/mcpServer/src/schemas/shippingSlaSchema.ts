import { z } from "zod";
import {
  deliveryTierStandard,
  deliveryTierExpress,
  deliveryTierSameDay
} from "../constants/protocolConstants.js";

export const shippingSlaRequestSchema = z.object({
  origin_pincode: z.string().regex(/^[1-9][0-9]{5}$/),
  delivery_pincode: z.string().regex(/^[1-9][0-9]{5}$/),
  package_weight_grams: z.number().int().min(1),
  required_delivery_tier: z.enum([
    deliveryTierStandard,
    deliveryTierExpress,
    deliveryTierSameDay
  ])
});

export type ShippingSlaRequest = z.infer<typeof shippingSlaRequestSchema>;

export const shippingSlaResponseSchema = z.object({
  guaranteed_sla_hours: z.number().int().positive(),
  shipping_cost_paise: z.number().int().min(0),
  courier_partner: z.string(),
  zone_code: z.string(),
  serviceable: z.boolean()
});

export type ShippingSlaResponse = z.infer<typeof shippingSlaResponseSchema>;
