import type { BadgeVariant } from '@/components/ui/Badge';
import type {
  Item,
  ItemCreateRequest,
  ItemUpdateRequest,
  StockMovement,
} from '@/types/api.types';
import { ItemStatus, ItemType, MovementDirection } from '@/types/enums';

import type { ItemCreateValues, ItemEditValues } from './item.schema';
import { ITEM_UNITS } from './item.schema';

export interface BadgeSpec {
  variant: BadgeVariant;
  label: string;
}

export function itemTypeBadge(type: ItemType): BadgeSpec {
  return type === ItemType.RAW
    ? { variant: 'info', label: 'RAW' }
    : { variant: 'purple', label: 'FINISHED' };
}

const STATUS_BADGE: Record<ItemStatus, BadgeSpec> = {
  [ItemStatus.IN_STOCK]: { variant: 'success', label: 'In stock' },
  [ItemStatus.LOW_STOCK]: { variant: 'warn', label: 'Low' },
  [ItemStatus.NO_STOCK]: { variant: 'danger', label: 'Out' },
};

export function itemStatusBadge(status: ItemStatus): BadgeSpec {
  return STATUS_BADGE[status];
}

/** Maps the UI status segmented-filter value → the Backend ItemStatus it means. */
export const STATUS_FILTER_TO_STATUS: Record<string, ItemStatus> = {
  ok: ItemStatus.IN_STOCK,
  low: ItemStatus.LOW_STOCK,
  out: ItemStatus.NO_STOCK,
};

export interface MovementSummary {
  lastMovementAt: string | null;
  totalInbound: number;
  totalOutbound: number;
}

/** Lifetime in/out totals + the most recent timestamp, for the detail stat cards. */
export function summariseMovements(movements: StockMovement[]): MovementSummary {
  let totalInbound = 0;
  let totalOutbound = 0;
  let lastMovementAt: string | null = null;
  for (const m of movements) {
    const qty = Number(m.quantity);
    if (m.direction === MovementDirection.IN) totalInbound += qty;
    else totalOutbound += qty;
    // created_at is ISO-8601 → lexicographic compare finds the latest.
    if (lastMovementAt === null || m.created_at > lastMovementAt) lastMovementAt = m.created_at;
  }
  return { lastMovementAt, totalInbound, totalOutbound };
}

/** Form → POST body, dropping empty optionals so the Backend keeps its defaults. */
export function toCreatePayload(values: ItemCreateValues): ItemCreateRequest {
  const payload: ItemCreateRequest = {
    sku: values.sku,
    name: values.name,
    type: values.type,
    category: values.category,
    unit_of_measure: values.unit_of_measure,
    unit_price: values.unit_price,
  };
  if (values.description) payload.description = values.description;
  if (values.stock_quantity) payload.stock_quantity = values.stock_quantity;
  if (values.reorder_threshold) payload.reorder_threshold = values.reorder_threshold;
  return payload;
}

/** Form → PATCH body. Only sends PATCH-safe fields (never sku/type/stock). */
export function toUpdatePayload(values: ItemEditValues): ItemUpdateRequest {
  const payload: ItemUpdateRequest = {
    name: values.name,
    category: values.category,
    unit_of_measure: values.unit_of_measure,
    unit_price: values.unit_price,
  };
  if (values.description) payload.description = values.description;
  if (values.reorder_threshold) payload.reorder_threshold = values.reorder_threshold;
  return payload;
}

function toFormUnit(unit: string): ItemEditValues['unit_of_measure'] {
  // The form select only offers ITEM_UNITS; fall back to the first if the
  // Backend ever returns an unknown unit (POC data uses the known set).
  return (ITEM_UNITS as readonly string[]).includes(unit)
    ? (unit as ItemEditValues['unit_of_measure'])
    : ITEM_UNITS[0];
}

/** Seeds the edit form from an existing item. */
export function itemToEditValues(item: Item): ItemEditValues {
  return {
    name: item.name,
    category: item.category ?? '',
    description: item.description ?? '',
    unit_of_measure: toFormUnit(item.unit_of_measure),
    reorder_threshold: item.reorder_threshold ?? '',
    unit_price: item.unit_price,
  };
}
