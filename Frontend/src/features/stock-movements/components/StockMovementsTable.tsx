import { Link } from 'react-router-dom';

import { routes } from '@/app/routes';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { Skeleton } from '@/components/ui/Skeleton';
import { formatDateTime, formatQuantity, formatSignedQuantity } from '@/lib/format';
import type { StockMovement } from '@/types/api.types';

import { directionBadge, movementReference, reasonLabel } from '../sm.transform';

const COL_COUNT = 8;
const SKELETON_ROWS = ['a', 'b', 'c', 'd', 'e'];
const REF_ROUTE = {
  'purchase-order': routes.purchaseOrders,
  'sales-order': routes.salesOrders,
} as const;

export interface StockMovementsTableProps {
  movements: StockMovement[];
  loading: boolean;
  itemName: (itemId: string) => string;
  /** Resolves the customer/vendor behind a movement (or an em dash). */
  party: (movement: StockMovement) => string;
  onAdjust: () => void;
}

/** Read-only audit ledger — no edit, no delete (§5 non-negotiable). */
export function StockMovementsTable({
  movements,
  loading,
  itemName,
  party,
  onAdjust,
}: StockMovementsTableProps): JSX.Element {
  return (
    <div className="tbl-wrap">
      <table className="tbl">
        <thead>
          <tr>
            <th>Time</th>
            <th>Item</th>
            <th>Direction</th>
            <th>Reason</th>
            <th>Customer / Vendor</th>
            <th className="right">Qty</th>
            <th className="right">Balance after</th>
            <th>Reference</th>
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
          ) : movements.length === 0 ? (
            <tr>
              <td colSpan={COL_COUNT}>
                <EmptyState
                  icon="swap"
                  title="No stock movements"
                  sub="Receiving POs, shipping SOs and manual adjustments all show up here."
                  action={
                    <Button variant="pri" icon="plus" onClick={onAdjust}>
                      Manual Adjustment
                    </Button>
                  }
                />
              </td>
            </tr>
          ) : (
            movements.map((m) => {
              const dir = directionBadge(m.direction);
              const ref = movementReference(m);
              return (
                <tr key={m.id}>
                  <td className="mono muted">{formatDateTime(m.created_at)}</td>
                  <td>
                    <Link
                      className="tbl-link"
                      to={`${routes.items}/${m.item_id}`}
                      state={{ from: routes.stockMovements, fromLabel: 'Stock Movements' }}
                    >
                      {itemName(m.item_id)}
                    </Link>
                  </td>
                  <td>
                    <Badge variant={dir.variant} dot>
                      {dir.label}
                    </Badge>
                  </td>
                  <td>
                    <Badge variant="ink">{reasonLabel(m.reason)}</Badge>
                  </td>
                  <td className="muted">{party(m)}</td>
                  <td className="right mono">{formatSignedQuantity(m.signed_quantity)}</td>
                  <td className="right mono">{formatQuantity(m.stock_after)}</td>
                  <td className="muted">
                    {ref.kind && ref.id ? (
                      <Link className="tbl-link" to={`${REF_ROUTE[ref.kind]}/${ref.id}`}>
                        {ref.label}
                      </Link>
                    ) : (
                      ref.label
                    )}
                  </td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
