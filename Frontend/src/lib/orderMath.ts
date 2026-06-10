/**
 * Pure money math for order line items (purchase + sales orders share this).
 * Quantities/prices arrive as strings; these are display estimates only — the
 * Backend computes the authoritative line/subtotal/total.
 */

export interface OrderLine {
  quantity: string;
  unit_price: string;
}

/** Per-line total when both qty and price are present (price may be Backend-filled). */
export function lineTotal(quantity: string, unitPrice: string): number | null {
  if (!quantity || !unitPrice) return null;
  const q = Number(quantity);
  const p = Number(unitPrice);
  if (!Number.isFinite(q) || !Number.isFinite(p)) return null;
  return q * p;
}

/** Sum of the priced lines — an estimate shown before submit. */
export function estimatedTotal(lines: OrderLine[]): number {
  return lines.reduce((sum, line) => sum + (lineTotal(line.quantity, line.unit_price) ?? 0), 0);
}
