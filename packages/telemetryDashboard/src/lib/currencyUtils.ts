const paisePerRupeeMultiplier = 100;
const defaultCurrencySymbol = "₹";
const defaultLocaleString = "en-IN";

export function formatPaiseToInr(paise: number | undefined | null): string {
  if (paise === undefined || paise === null || isNaN(paise)) {
    return `${defaultCurrencySymbol}0.00`;
  }
  const rupees = paise / paisePerRupeeMultiplier;
  return new Intl.NumberFormat(defaultLocaleString, {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(rupees);
}

export function formatPaiseToCompactInr(paise: number | undefined | null): string {
  if (paise === undefined || paise === null || isNaN(paise)) {
    return `${defaultCurrencySymbol}0.00`;
  }
  const rupees = paise / paisePerRupeeMultiplier;
  if (rupees >= 10000000) {
    const crValue = rupees / 10000000;
    const formattedCr = (crValue * 10) % 1 === 0 ? crValue.toFixed(1) : crValue.toFixed(2);
    return `${defaultCurrencySymbol}${formattedCr} Cr`;
  }
  if (rupees >= 100000) {
    return `${defaultCurrencySymbol}${(rupees / 100000).toFixed(2)} L`;
  }
  if (rupees >= 1000) {
    return `${defaultCurrencySymbol}${(rupees / 1000).toFixed(1)}k`;
  }
  return formatPaiseToInr(paise);
}

export function computePercentageDelta(originalPaise: number, substitutePaise: number): string {
  if (originalPaise <= 0) {
    return "+0.0%";
  }
  const deltaPaise = substitutePaise - originalPaise;
  const percentage = (deltaPaise / originalPaise) * 100;
  const prefix = percentage >= 0 ? "+" : "";
  return `${prefix}${percentage.toFixed(1)}%`;
}

export function formatLatency(durationMs: number | undefined | null): string {
  if (durationMs === undefined || durationMs === null || isNaN(durationMs) || durationMs === 0) {
    return "0ms";
  }
  if (durationMs < 1) {
    return `${(durationMs * 1000).toFixed(0)}µs`;
  }
  if (durationMs < 10 && durationMs % 1 !== 0) {
    return `${durationMs.toFixed(1)}ms`;
  }
  return `${durationMs.toFixed(0)}ms`;
}

