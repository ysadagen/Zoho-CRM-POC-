import type { BadgeVariant } from '@/components/ui/Badge';
import type { ManualAdjustmentRequest, StockMovement } from '@/types/api.types';
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

export function toAdjustmentPayload(values: AdjustmentValues): ManualAdjustmentRequest {
  return {
    item_id: values.item_id,
    direction: values.direction,
    quantity: values.quantity,
    remarks: values.remarks,
  };
}
