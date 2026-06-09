import { Link } from 'react-router-dom';

import { routes } from '@/app/routes';
import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { Skeleton } from '@/components/ui/Skeleton';
import { formatDate } from '@/lib/format';
import type { Vendor } from '@/types/api.types';

const COL_COUNT = 6;
const SKELETON_ROWS = ['a', 'b', 'c', 'd', 'e'];

export interface VendorsTableProps {
  vendors: Vendor[];
  loading: boolean;
  onEdit: (vendor: Vendor) => void;
  onAdd: () => void;
}

export function VendorsTable({ vendors, loading, onEdit, onAdd }: VendorsTableProps): JSX.Element {
  return (
    <div className="tbl-wrap">
      <table className="tbl">
        <thead>
          <tr>
            <th>Vendor</th>
            <th>Contact</th>
            <th>Email</th>
            <th>Phone</th>
            <th>Created</th>
            <th className="right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {loading ? (
            SKELETON_ROWS.map((key) => (
              <tr key={key}>
                <td colSpan={COL_COUNT}>
                  <Skeleton height={18} />
                </td>
              </tr>
            ))
          ) : vendors.length === 0 ? (
            <tr>
              <td colSpan={COL_COUNT}>
                <EmptyState
                  icon="truck"
                  title="No vendors found"
                  sub="Try a different search, or add your first vendor."
                  action={
                    <Button variant="pri" icon="plus" onClick={onAdd}>
                      Add Vendor
                    </Button>
                  }
                />
              </td>
            </tr>
          ) : (
            vendors.map((vendor) => (
              <tr key={vendor.id}>
                <td>
                  <Link className="tbl-link" to={`${routes.vendors}/${vendor.id}`}>
                    {vendor.vendor_name}
                  </Link>
                </td>
                <td className="muted">{vendor.contact_person ?? '—'}</td>
                <td className="muted">{vendor.email ?? '—'}</td>
                <td className="muted">{vendor.phone ?? '—'}</td>
                <td className="muted">{formatDate(vendor.created_at)}</td>
                <td className="right">
                  <Link className="btn btn-txt btn-sm" to={`${routes.vendors}/${vendor.id}`}>
                    View
                  </Link>
                  <button className="btn btn-txt btn-sm" type="button" onClick={() => onEdit(vendor)}>
                    Edit
                  </button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
