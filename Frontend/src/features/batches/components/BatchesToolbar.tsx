import type { Item } from '@/types/api.types';
import type { BatchStatus } from '@/types/enums';

import { BATCH_STATUS_OPTIONS } from '../batch.transform';

export type StatusFilter = BatchStatus | '';

export interface BatchesToolbarProps {
  itemId: string;
  onItem: (value: string) => void;
  items: Item[];
  status: StatusFilter;
  onStatus: (value: StatusFilter) => void;
  expiringBefore: string;
  onExpiringBefore: (value: string) => void;
}

export function BatchesToolbar({
  itemId,
  onItem,
  items,
  status,
  onStatus,
  expiringBefore,
  onExpiringBefore,
}: BatchesToolbarProps): JSX.Element {
  // The status <select> only renders StatusFilter option values, so casting
  // e.target.value to StatusFilter is sound.
  return (
    <div className="toolbar">
      <select
        className="select field-auto"
        value={itemId}
        onChange={(e) => onItem(e.target.value)}
        aria-label="Filter by item"
      >
        <option value="">All items</option>
        {items.map((item) => (
          <option key={item.id} value={item.id}>
            {item.sku} — {item.name}
          </option>
        ))}
      </select>

      <select
        className="select field-auto"
        value={status}
        onChange={(e) => onStatus(e.target.value as StatusFilter)}
        aria-label="Filter by status"
      >
        <option value="">All statuses</option>
        {BATCH_STATUS_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>

      <label className="flex items-center gap-8 text-muted fs-12">
        Expiring before
        <input
          className="input field-auto"
          type="date"
          value={expiringBefore}
          onChange={(e) => onExpiringBefore(e.target.value)}
          aria-label="Expiring before date"
        />
      </label>

      <span className="spacer" />
    </div>
  );
}
