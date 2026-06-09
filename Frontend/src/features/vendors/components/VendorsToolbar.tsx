import { Icon } from '@/components/ui/Icon';

export interface VendorsToolbarProps {
  search: string;
  onSearch: (value: string) => void;
}

export function VendorsToolbar({ search, onSearch }: VendorsToolbarProps): JSX.Element {
  return (
    <div className="toolbar">
      <div className="search">
        <Icon name="search" size={16} />
        <input
          type="search"
          placeholder="Search vendor or code"
          aria-label="Search vendors"
          value={search}
          onChange={(e) => onSearch(e.target.value)}
        />
      </div>
      <span className="spacer" />
    </div>
  );
}
