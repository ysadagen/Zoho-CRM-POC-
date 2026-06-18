import { Segmented, type SegmentedOption } from '@/components/ui/Segmented';
import type { Vendor } from '@/types/api.types';

export type PoStatusFilter = 'ALL' | 'DRAFT' | 'RECEIVED';

const STATUS_OPTIONS: SegmentedOption<PoStatusFilter>[] = [
  { value: 'ALL', label: 'All' },
  { value: 'DRAFT', label: 'Draft' },
  { value: 'RECEIVED', label: 'Received' },
];

export interface PurchaseOrdersToolbarProps {
  status: PoStatusFilter;
  onStatus: (value: PoStatusFilter) => void;
  vendorId: string;
  onVendor: (value: string) => void;
  vendors: Vendor[];
}

export function PurchaseOrdersToolbar({
  status,
  onStatus,
  vendorId,
  onVendor,
  vendors,
}: PurchaseOrdersToolbarProps): JSX.Element {
  return (
    <div className="toolbar">
      <Segmented options={STATUS_OPTIONS} value={status} onChange={onStatus} ariaLabel="Filter by status" />
      <select
        className="select field-auto"
        value={vendorId}
        onChange={(e) => onVendor(e.target.value)}
        aria-label="Filter by vendor"
      >
        <option value="">All vendors</option>
        {vendors.map((vendor) => (
          <option key={vendor.id} value={vendor.id}>
            {vendor.vendor_name}
          </option>
        ))}
      </select>
      <span className="spacer" />
    </div>
  );
}
