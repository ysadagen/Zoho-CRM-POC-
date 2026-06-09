import { Badge } from '@/components/ui/Badge';
import { EmptyState } from '@/components/ui/EmptyState';
import { Skeleton } from '@/components/ui/Skeleton';
import { formatCurrency, formatDate } from '@/lib/format';
import type { PurchaseOrder } from '@/types/api.types';
import { PurchaseOrderStatus } from '@/types/enums';

const COL_COUNT = 4;
const SKELETON_ROWS = ['a', 'b', 'c'];

export interface VendorPurchaseOrdersTabProps {
  orders: PurchaseOrder[];
  loading: boolean;
}

export function VendorPurchaseOrdersTab({ orders, loading }: VendorPurchaseOrdersTabProps): JSX.Element {
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

  if (orders.length === 0) {
    return (
      <div className="card">
        <EmptyState
          icon="cart"
          title="No purchase orders yet"
          sub="Purchase orders raised with this vendor will appear here."
        />
      </div>
    );
  }

  return (
    <div className="card tbl-wrap">
      <table className="tbl">
        <thead>
          <tr>
            <th>PO number</th>
            <th>Order date</th>
            <th>Status</th>
            <th className="right">Total</th>
          </tr>
        </thead>
        <tbody>
          {orders.map((po) => (
            <tr key={po.id}>
              <td className="mono">{po.po_number}</td>
              <td className="muted">{formatDate(po.order_date)}</td>
              <td>
                <Badge variant={po.status === PurchaseOrderStatus.RECEIVED ? 'success' : 'ink'} dot>
                  {po.status}
                </Badge>
              </td>
              <td className="right mono">{formatCurrency(po.total)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
