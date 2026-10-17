/**
 * Locale-safe number formatting utilities for chart labels.
 * .toFixed() can use comma as decimal separator in some locales (e.g., Turkish, German).
 * Always use these instead of direct .toFixed() calls.
 */

/** Format a number to N decimal places using "." as the decimal separator */
export function toFixed(value: number, decimals = 1): string {
  // Use toLocaleString with explicit en-US locale to guarantee "." as decimal
  return value.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

/** Format a percentage value (e.g., 6.3 → "6.3%") */
export function toPct(value: number, decimals = 1): string {
  return `${toFixed(value, decimals)}%`;
}
