import { Icon } from '@/components/ui/Icon';

export interface CustomersToolbarProps {
  search: string;
  onSearch: (value: string) => void;
}

export function CustomersToolbar({ search, onSearch }: CustomersToolbarProps): JSX.Element {
  return (
    <div className="toolbar">
      <div className="search">
        <Icon name="search" size={16} />
        <input
          type="search"
          placeholder="Search company or code"
          aria-label="Search customers"
          value={search}
          onChange={(e) => onSearch(e.target.value)}
        />
      </div>
      <span className="spacer" />
    </div>
  );
}
