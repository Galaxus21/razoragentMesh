// Defaults applied when the SDK omits an optional query parameter. `defaultSlaWeightGrams`
// mirrors `defaultSlaWeightGrams` in buyerSdkTs/src/sdkConstants.ts so that an SDK call with
// no explicit weight and a direct cURL with no weight produce the same quote.
export const defaultSlaWeightGrams = 500;
export const defaultQuoteQuantity = 1;
