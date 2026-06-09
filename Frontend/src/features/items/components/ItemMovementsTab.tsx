import { Badge } from '@/components/ui/Badge';
import { EmptyState } from '@/components/ui/EmptyState';
import { Skeleton } from '@/components/ui/Skeleton';
import { formatDateTime, formatQuantity, formatSignedQuantity } from '@/lib/format';
import type { StockMovement } from '@/types/api.types';
import { MovementDirection, MovementReason } from '@/types/enums';

const COL_COUNT = 6;
const SKELETON_ROWS = ['a', 'b', 'c'];

const REASON_LABEL: Record<string, string> = {
  [MovementReason.PURCHASE]: 'Purchase',
  [MovementReason.SALE]: 'Sale',
  [MovementReason.ADJUSTMENT]: 'Adjustment',
};

function referenceLabel(m: StockMovement): string {
  if (m.reference_type === 'PURCHASE_ORDER') return 'Purchase order';
  if (m.reference_type === 'SALES_ORDER') return 'Sales order';
  return m.remarks ?? '—';
}

export interface ItemMovementsTabProps {
  movements: StockMovement[];
  unit: string;
  loading: boolean;
}

export function ItemMovementsTab({ movements, unit, loading }: ItemMovementsTabProps): JSX.Element {
  if (loading) {
    return (
      <div className="card tbl-wrap">
        <table className="tbl">
          <tbody>
            {SKELETON_ROWS.map((key) => (
              <tr key={key}>
                <td colSpan={COL_COUNT}>
                  <Skeleton height={16} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  if (movements.length === 0) {
    return (
      <div className="card">
        <EmptyState
          icon="swap"
          title="No movements yet"
          sub="Stock changes for this item will appear here once it is bought, sold or adjusted."
        />
      </div>
    );
  }

  return (
    <div className="card tbl-wrap">
      <table className="tbl">
        <thead>
          <tr>
            <th>Time</th>
            <th>Direction</th>
            <th>Reason</th>
            <th className="right">Qty</th>
            <th className="right">Balance after</th>
            <th>Reference</th>
          </tr>
        </thead>
        <tbody>
          {movements.map((m) => (
            <tr key={m.id}>
              <td className="mono muted">{formatDateTime(m.created_at)}</td>
              <td>
                <Badge variant={m.direction === MovementDirection.IN ? 'success' : 'danger'} dot>
                  {m.direction}
                </Badge>
              </td>
              <td className="muted">{REASON_LABEL[m.reason] ?? m.reason}</td>
              <td className="right mono">{formatSignedQuantity(m.signed_quantity, unit)}</td>
              <td className="right mono">{formatQuantity(m.stock_after, unit)}</td>
              <td className="muted">{referenceLabel(m)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
