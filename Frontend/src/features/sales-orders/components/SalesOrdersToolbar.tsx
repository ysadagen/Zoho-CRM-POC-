import { Segmented, type SegmentedOption } from '@/components/ui/Segmented';
import type { Customer } from '@/types/api.types';

export type SoStatusFilter = 'ALL' | 'DRAFT' | 'SHIPPED';

const STATUS_OPTIONS: SegmentedOption<SoStatusFilter>[] = [
  { value: 'ALL', label: 'All' },
  { value: 'DRAFT', label: 'Draft' },
  { value: 'SHIPPED', label: 'Shipped' },
];

export interface SalesOrdersToolbarProps {
  status: SoStatusFilter;
  onStatus: (value: SoStatusFilter) => void;
  customerId: string;
  onCustomer: (value: string) => void;
  customers: Customer[];
}

export function SalesOrdersToolbar({
  status,
  onStatus,
  customerId,
  onCustomer,
  customers,
}: SalesOrdersToolbarProps): JSX.Element {
  return (
    <div className="toolbar">
      <Segmented options={STATUS_OPTIONS} value={status} onChange={onStatus} ariaLabel="Filter by status" />
      <select
        className="select"
        style={{ width: 'auto', minHeight: 'auto' }}
        value={customerId}
        onChange={(e) => onCustomer(e.target.value)}
        aria-label="Filter by customer"
      >
        <option value="">All customers</option>
        {customers.map((customer) => (
          <option key={customer.id} value={customer.id}>
            {customer.company_name}
          </option>
        ))}
      </select>
      <span className="spacer" />
    </div>
  );
}
