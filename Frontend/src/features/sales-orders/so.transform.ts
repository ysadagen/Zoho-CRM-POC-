import type { BadgeVariant } from '@/components/ui/Badge';
import type { StockChipVariant } from '@/components/ui/StockChip';
import { formatQuantity } from '@/lib/format';
import type { Batch, Item, SalesOrder, SalesOrderCreateRequest } from '@/types/api.types';
import { SalesOrderStatus } from '@/types/enums';

import type { SoFormValues } from './so.schema';

// Generic order-line math is shared with purchase orders (lib/orderMath).
export { estimatedTotal, lineTotal } from '@/lib/orderMath';

export function soStatusBadge(status: SalesOrderStatus): { variant: BadgeVariant; label: string } {
  return status === SalesOrderStatus.SHIPPED
    ? { variant: 'success', label: 'Shipped' }
    : { variant: 'ink', label: 'Draft' };
}

export function toSoCreatePayload(values: SoFormValues): SalesOrderCreateRequest {
  const payload: SalesOrderCreateRequest = {
    customer_id: values.customer_id,
    items: values.items.map((line) => {
      const out: SalesOrderCreateRequest['items'][number] = {
        item_id: line.item_id,
        quantity: line.quantity,
      };
      if (line.unit_price) out.unit_price = line.unit_price;
      if (line.batch_id) out.batch_id = line.batch_id;
      return out;
    }),
  };
  if (values.expected_delivery_date) payload.expected_delivery_date = values.expected_delivery_date;
  if (values.notes) payload.notes = values.notes;
  return payload;
}

export interface StockChipState {
  variant: StockChipVariant;
  label: string;
}

/**
 * Live stock state for one SO line (§5 non-negotiable). Returns null when no
 * item is picked yet. `short` = qty exceeds current stock; `warn` = fulfilling
 * drops below the reorder threshold; otherwise `ok`.
 */
export function soLineStock(quantity: string, item: Item | undefined): StockChipState | null {
  if (!item) return null;
  const stock = Number(item.stock_quantity);
  const qty = Number(quantity || '0');
  const unit = item.unit_of_measure;
  if (qty > stock) {
    return {
      variant: 'short',
      label: `Only ${formatQuantity(stock)} ${unit} — short by ${formatQuantity(qty - stock)}`,
    };
  }
  const reorder = item.reorder_threshold == null ? null : Number(item.reorder_threshold);
  if (qty > 0 && reorder != null && stock - qty < reorder) {
    return { variant: 'warn', label: `${formatQuantity(stock)} ${unit} — low after this` };
  }
  return { variant: 'ok', label: `${formatQuantity(stock)} ${unit} in stock` };
}

/** True if any line orders more than the item's current stock (blocks Create). */
export function hasShortLine(lines: SoFormValues['items'], items: Map<string, Item>): boolean {
  return lines.some((line) => {
    const item = items.get(line.item_id);
    if (!item) return false;
    return Number(line.quantity || '0') > Number(item.stock_quantity);
  });
}

/**
 * Group an item's *shippable* lots (in stock, not expired) by item_id, for the
 * SO line "Ship from lot" picker (#9). Earliest-expiry first so the listing
 * follows FEFO order. `asOf` defaults to today (ISO yyyy-mm-dd).
 */
export function shippableLotsByItem(
  batches: Batch[],
  asOf: string = new Date().toISOString().slice(0, 10),
): Map<string, Batch[]> {
  const byItem = new Map<string, Batch[]>();
  for (const lot of batches) {
    if (Number(lot.quantity) <= 0 || lot.expiry_date < asOf) continue;
    const list = byItem.get(lot.item_id) ?? [];
    list.push(lot);
    byItem.set(lot.item_id, list);
  }
  for (const list of byItem.values()) {
    list.sort((a, b) => a.expiry_date.localeCompare(b.expiry_date));
  }
  return byItem;
}

export interface ShipDelta {
  itemId: string;
  label: string;
}

/** "-120 pcs Bottle 1L" lines for the ship confirmation modal. */
export function shipDeltas(so: SalesOrder, items: Map<string, Item>): ShipDelta[] {
  return so.items.map((line) => {
    const item = items.get(line.item_id);
    const unit = item ? ` ${item.unit_of_measure}` : '';
    const name = item ? item.name : line.item_id;
    return { itemId: line.item_id, label: `-${line.quantity}${unit} ${name}` };
  });
}
