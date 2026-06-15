import type { BadgeVariant } from '@/components/ui/Badge';
import type { BatchCreateRequest } from '@/types/api.types';
import { BatchStatus } from '@/types/enums';

import type { BatchFormValues } from './batch.schema';

export interface BadgeSpec {
  variant: BadgeVariant;
  label: string;
}

/** Canonical batch_status → badge mapping (Design System §9). */
const STATUS_BADGE: Record<BatchStatus, BadgeSpec> = {
  [BatchStatus.QUARANTINE]: { variant: 'warn', label: 'Quarantine' },
  [BatchStatus.RELEASED]: { variant: 'success', label: 'Released' },
  [BatchStatus.EXPIRED]: { variant: 'danger', label: 'Expired' },
  [BatchStatus.REJECTED]: { variant: 'danger', label: 'Rejected' },
  [BatchStatus.RECALLED]: { variant: 'danger', label: 'Recalled' },
};

export function batchStatusBadge(status: BatchStatus): BadgeSpec {
  return STATUS_BADGE[status];
}

/** Options for the status select / filter. */
export const BATCH_STATUS_OPTIONS: { value: BatchStatus; label: string }[] = (
  Object.keys(STATUS_BADGE) as BatchStatus[]
).map((value) => ({ value, label: STATUS_BADGE[value].label }));

/** Form → POST body, dropping blank optionals. */
export function toBatchCreatePayload(values: BatchFormValues): BatchCreateRequest {
  const payload: BatchCreateRequest = {
    item_id: values.item_id,
    batch_number: values.batch_number,
    expiry_date: values.expiry_date,
    quantity: values.quantity,
    batch_status: values.batch_status,
  };
  if (values.manufacturing_date) payload.manufacturing_date = values.manufacturing_date;
  if (values.unit_cost) payload.unit_cost = values.unit_cost;
  if (values.storage_location) payload.storage_location = values.storage_location;
  return payload;
}
