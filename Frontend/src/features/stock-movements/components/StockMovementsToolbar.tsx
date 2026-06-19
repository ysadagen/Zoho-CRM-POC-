import { Segmented, type SegmentedOption } from '@/components/ui/Segmented';
import type { Item } from '@/types/api.types';

export type DirectionFilter = 'ALL' | 'IN' | 'OUT';
export type ReasonFilter = 'ALL' | 'PURCHASE' | 'SALE' | 'ADJUSTMENT';

const DIRECTION_OPTIONS: SegmentedOption<DirectionFilter>[] = [
  { value: 'ALL', label: 'All' },
  { value: 'IN', label: 'IN' },
  { value: 'OUT', label: 'OUT' },
];

const REASON_OPTIONS: SegmentedOption<ReasonFilter>[] = [
  { value: 'ALL', label: 'All' },
  { value: 'PURCHASE', label: 'Purchase' },
  { value: 'SALE', label: 'Sale' },
  { value: 'ADJUSTMENT', label: 'Adjustment' },
];

export interface StockMovementsToolbarProps {
  itemId: string;
  onItem: (value: string) => void;
  items: Item[];
  direction: DirectionFilter;
  onDirection: (value: DirectionFilter) => void;
  reason: ReasonFilter;
  onReason: (value: ReasonFilter) => void;
}

export function StockMovementsToolbar({
  itemId,
  onItem,
  items,
  direction,
  onDirection,
  reason,
  onReason,
}: StockMovementsToolbarProps): JSX.Element {
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
      <Segmented
        options={DIRECTION_OPTIONS}
        value={direction}
        onChange={onDirection}
        ariaLabel="Filter by direction"
      />
      <Segmented
        options={REASON_OPTIONS}
        value={reason}
        onChange={onReason}
        ariaLabel="Filter by reason"
      />
      <span className="spacer" />
    </div>
  );
}
