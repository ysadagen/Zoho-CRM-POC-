import { Link } from 'react-router-dom';

import { routes } from '@/app/routes';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { Skeleton } from '@/components/ui/Skeleton';
import { formatCurrency, formatDate, formatQuantity } from '@/lib/format';
import type { Batch } from '@/types/api.types';

import { BatchStatusBadge } from './BatchStatusBadge';

const COL_COUNT = 6;
const SKELETON_ROWS = ['a', 'b', 'c', 'd', 'e'];

export interface BatchesTableProps {
  batches: Batch[];
  loading: boolean;
  itemName: (itemId: string) => string;
  onAdd: () => void;
}

export function BatchesTable({ batches, loading, itemName, onAdd }: BatchesTableProps): JSX.Element {
  return (
    <div className="tbl-wrap">
      <table className="tbl">
        <thead>
          <tr>
            <th>Item</th>
            <th>Batch no.</th>
            <th>Status</th>
            <th>Expiry</th>
            <th className="right">Quantity</th>
            <th>Location</th>
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
          ) : batches.length === 0 ? (
            <tr>
              <td colSpan={COL_COUNT}>
                <EmptyState
                  icon="package"
                  title="No lots yet"
                  sub="Record an opening-balance lot, or receive a purchase order to create lots."
                  action={
                    <Button variant="pri" icon="plus" onClick={onAdd}>
                      New Lot
                    </Button>
                  }
                />
              </td>
            </tr>
          ) : (
            batches.map((batch) => (
              <tr key={batch.id}>
                <td>
                  <Link className="tbl-link" to={`${routes.items}/${batch.item_id}`}>
                    {itemName(batch.item_id)}
                  </Link>
                </td>
                <td className="mono">{batch.batch_number}</td>
                <td>
                  <BatchStatusBadge status={batch.batch_status} />
                </td>
                <td className="mono muted">
                  <span className="flex items-center gap-8">
                    {formatDate(batch.expiry_date)}
                    {batch.is_expired && <Badge variant="danger">Expired</Badge>}
                  </span>
                </td>
                <td className="right mono">{formatQuantity(batch.quantity)}</td>
                <td className="muted">
                  {batch.storage_location ?? '—'}
                  {batch.unit_cost ? ` · ${formatCurrency(batch.unit_cost)}` : ''}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
