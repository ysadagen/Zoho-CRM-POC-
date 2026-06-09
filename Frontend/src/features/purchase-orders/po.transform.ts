import type { BadgeVariant } from '@/components/ui/Badge';
import type {
  Item,
  PurchaseOrder,
  PurchaseOrderCreateRequest,
} from '@/types/api.types';
import { PurchaseOrderStatus } from '@/types/enums';

import type { PoFormValues } from './po.schema';

// Generic order-line math is shared with sales orders (lib/orderMath).
export { estimatedTotal, lineTotal } from '@/lib/orderMath';

export function poStatusBadge(status: PurchaseOrderStatus): { variant: BadgeVariant; label: string } {
  return status === PurchaseOrderStatus.RECEIVED
    ? { variant: 'success', label: 'Received' }
    : { variant: 'ink', label: 'Draft' };
}

/** Form → POST body. Drops blank optionals (so the Backend applies its defaults). */
export function toPoCreatePayload(values: PoFormValues): PurchaseOrderCreateRequest {
  const payload: PurchaseOrderCreateRequest = {
    vendor_id: values.vendor_id,
    items: values.items.map((line) => {
      const out: PurchaseOrderCreateRequest['items'][number] = {
        item_id: line.item_id,
        quantity: line.quantity,
      };
      if (line.unit_price) out.unit_price = line.unit_price;
      return out;
    }),
  };
  if (values.expected_delivery_date) payload.expected_delivery_date = values.expected_delivery_date;
  if (values.notes) payload.notes = values.notes;
  return payload;
}

export interface ReceiveDelta {
  itemId: string;
  label: string;
}

/** "+100 kg Raw Plastic" lines for the receive confirmation modal. */
export function receiveDeltas(po: PurchaseOrder, items: Map<string, Item>): ReceiveDelta[] {
  return po.items.map((line) => {
    const item = items.get(line.item_id);
    const unit = item ? ` ${item.unit_of_measure}` : '';
    const name = item ? item.name : line.item_id;
    return { itemId: line.item_id, label: `+${line.quantity}${unit} ${name}` };
  });
}
