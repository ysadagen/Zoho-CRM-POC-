import { Link } from 'react-router-dom';

import { routes } from '@/app/routes';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { Skeleton } from '@/components/ui/Skeleton';
import { formatCurrency, formatDate, formatQuantity } from '@/lib/format';
import type { Batch } from '@/types/api.types';
import { BatchStatus } from '@/types/enums';

import { BatchStatusBadge } from './BatchStatusBadge';

const COL_COUNT = 8;
const SKELETON_ROWS = ['a', 'b', 'c', 'd', 'e'];

interface QcAction {
  label: string;
  status: BatchStatus;
  variant: 'pri' | 'dng';
}

/** Legal QC moves for the lot's current status (mirrors the Backend, #7). */
function qcActions(status: BatchStatus): QcAction[] {
  switch (status) {
    case BatchStatus.QUARANTINE:
      return [
        { label: 'Release', status: BatchStatus.RELEASED, variant: 'pri' },
        { label: 'Reject', status: BatchStatus.REJECTED, variant: 'dng' },
      ];
    case BatchStatus.RELEASED:
      return [{ label: 'Recall', status: BatchStatus.RECALLED, variant: 'dng' }];
    default:
      return [];
  }
}

export interface BatchesTableProps {
  batches: Batch[];
  loading: boolean;
  itemName: (itemId: string) => string;
  onAdd: () => void;
  onChangeStatus: (batch: Batch, status: BatchStatus) => void;
  busyId?: string | null;
}

export function BatchesTable({
  batches,
  loading,
  itemName,
  onAdd,
  onChangeStatus,
  busyId,
}: BatchesTableProps): JSX.Element {
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
            <th className="right">Unit Cost</th>
            <th aria-label="QC actions" />
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
                <td className="muted">{batch.storage_location ?? '—'}</td>
                <td className="right muted">
                  {batch.unit_cost ? formatCurrency(batch.unit_cost) : '—'}
                </td>
                <td className="right">
                  <span className="flex gap-8 justify-end">
                    {qcActions(batch.batch_status).map((action) => (
                      <Button
                        key={action.status}
                        variant={action.variant}
                        size="sm"
                        disabled={busyId === batch.id}
                        onClick={() => onChangeStatus(batch, action.status)}
                      >
                        {action.label}
                      </Button>
                    ))}
                  </span>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
