import { Icon } from '@/components/ui/Icon';
import { Segmented, type SegmentedOption } from '@/components/ui/Segmented';

export type TypeFilter = 'ALL' | 'RAW' | 'FINISHED';
export type StatusFilter = 'all' | 'ok' | 'low' | 'out';

const TYPE_OPTIONS: SegmentedOption<TypeFilter>[] = [
  { value: 'ALL', label: 'All' },
  { value: 'RAW', label: 'Raw' },
  { value: 'FINISHED', label: 'Finished' },
];

const STATUS_OPTIONS: SegmentedOption<StatusFilter>[] = [
  { value: 'all', label: 'All' },
  { value: 'ok', label: 'OK' },
  { value: 'low', label: 'Low' },
  { value: 'out', label: 'Out' },
];

export interface ItemsToolbarProps {
  search: string;
  onSearch: (value: string) => void;
  type: TypeFilter;
  onType: (value: TypeFilter) => void;
  status: StatusFilter;
  onStatus: (value: StatusFilter) => void;
}

export function ItemsToolbar({
  search,
  onSearch,
  type,
  onType,
  status,
  onStatus,
}: ItemsToolbarProps): JSX.Element {
  return (
    <div className="toolbar">
      <div className="search">
        <Icon name="search" size={16} />
        <input
          type="search"
          placeholder="Search SKU or name"
          aria-label="Search items"
          value={search}
          onChange={(e) => onSearch(e.target.value)}
        />
      </div>
      <Segmented options={TYPE_OPTIONS} value={type} onChange={onType} ariaLabel="Filter by type" />
      <Segmented
        options={STATUS_OPTIONS}
        value={status}
        onChange={onStatus}
        ariaLabel="Filter by stock status"
      />
      <span className="spacer" />
    </div>
  );
}
