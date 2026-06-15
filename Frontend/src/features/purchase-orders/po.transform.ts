import type { BadgeVariant } from '@/components/ui/Badge';
import type {
  PurchaseOrder,
  PurchaseOrderCreateRequest,
  PurchaseOrderReceiveLine,
  PurchaseOrderReceiveRequest,
} from '@/types/api.types';
import { PurchaseOrderStatus } from '@/types/enums';

import type { PoFormValues, PoReceiveValues } from './po.schema';

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

/** Seed the receive form: one blank lot row per PO line (item_id prefilled). */
export function receiveDefaults(po: PurchaseOrder): PoReceiveValues {
  return {
    lines: po.items.map((line) => ({
      item_id: line.item_id,
      batch_number: '',
      expiry_date: '',
      manufacturing_date: '',
      storage_location: '',
    })),
  };
}

/** Receive form → POST body, dropping blank optionals. */
export function toReceivePayload(values: PoReceiveValues): PurchaseOrderReceiveRequest {
  return {
    lines: values.lines.map((line) => {
      const out: PurchaseOrderReceiveLine = {
        item_id: line.item_id,
        batch_number: line.batch_number,
        expiry_date: line.expiry_date,
      };
      if (line.manufacturing_date) out.manufacturing_date = line.manufacturing_date;
      if (line.storage_location) out.storage_location = line.storage_location;
      return out;
    }),
  };
}
