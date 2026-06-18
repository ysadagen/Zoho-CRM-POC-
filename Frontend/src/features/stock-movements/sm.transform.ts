import type { BadgeVariant } from '@/components/ui/Badge';
import type {
  Customer,
  ManualAdjustmentRequest,
  PurchaseOrder,
  SalesOrder,
  StockMovement,
  Vendor,
} from '@/types/api.types';
import { MovementDirection, MovementReason, MovementReferenceType } from '@/types/enums';

import type { AdjustmentValues } from './sm.schema';

export function directionBadge(direction: MovementDirection): { variant: BadgeVariant; label: string } {
  return direction === MovementDirection.IN
    ? { variant: 'success', label: 'IN ↑' }
    : { variant: 'danger', label: 'OUT ↓' };
}

const REASON_LABEL: Record<MovementReason, string> = {
  [MovementReason.PURCHASE]: 'Purchase',
  [MovementReason.SALE]: 'Sale',
  [MovementReason.ADJUSTMENT]: 'Adjustment',
};

export function reasonLabel(reason: MovementReason): string {
  return REASON_LABEL[reason] ?? reason;
}

export interface MovementRef {
  label: string;
  /** Feature kind for the link target, or null when there's nothing to link. */
  kind: 'purchase-order' | 'sales-order' | null;
  id: string | null;
}

/** Resolves a movement's reference to a linkable PO/SO, else its remarks. */
export function movementReference(m: StockMovement): MovementRef {
  if (m.reference_type === MovementReferenceType.PURCHASE_ORDER && m.reference_id) {
    return { label: 'Purchase order', kind: 'purchase-order', id: m.reference_id };
  }
  if (m.reference_type === MovementReferenceType.SALES_ORDER && m.reference_id) {
    return { label: 'Sales order', kind: 'sales-order', id: m.reference_id };
  }
  return { label: m.remarks ?? '—', kind: null, id: null };
}

/** Lookups for resolving a movement's reference to its trading party. */
export interface PartyMaps {
  purchaseOrders: Map<string, PurchaseOrder>;
  salesOrders: Map<string, SalesOrder>;
  vendors: Map<string, Vendor>;
  customers: Map<string, Customer>;
}

/**
 * Resolves the customer/vendor behind a movement: PURCHASE → vendor on the PO,
 * SALE → customer on the SO, ADJUSTMENT (or any unresolved ref) → em dash.
 */
export function movementParty(m: StockMovement, maps: PartyMaps): string {
  if (m.reference_type === MovementReferenceType.PURCHASE_ORDER && m.reference_id) {
    const po = maps.purchaseOrders.get(m.reference_id);
    return (po && maps.vendors.get(po.vendor_id)?.vendor_name) ?? '—';
  }
  if (m.reference_type === MovementReferenceType.SALES_ORDER && m.reference_id) {
    const so = maps.salesOrders.get(m.reference_id);
    return (so && maps.customers.get(so.customer_id)?.company_name) ?? '—';
  }
  return '—';
}

export function toAdjustmentPayload(values: AdjustmentValues): ManualAdjustmentRequest {
  const payload: ManualAdjustmentRequest = {
    item_id: values.item_id,
    direction: values.direction,
    quantity: values.quantity,
    remarks: values.remarks,
  };
  if (values.batch_id) payload.batch_id = values.batch_id;
  return payload;
}
