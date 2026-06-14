import { Badge } from '@/components/ui/Badge';
import { EmptyState } from '@/components/ui/EmptyState';
import { Skeleton } from '@/components/ui/Skeleton';
import { formatCurrency, formatDate } from '@/lib/format';
import type { SalesOrder } from '@/types/api.types';
import { SalesOrderStatus } from '@/types/enums';

const COL_COUNT = 4;
const SKELETON_ROWS = ['a', 'b', 'c'];

export interface CustomerSalesOrdersTabProps {
  orders: SalesOrder[];
  loading: boolean;
}

export function CustomerSalesOrdersTab({ orders, loading }: CustomerSalesOrdersTabProps): JSX.Element {
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
          icon="bag"
          title="No sales orders yet"
          sub="Sales orders placed by this customer will appear here."
        />
      </div>
    );
  }

  return (
    <div className="card tbl-wrap">
      <table className="tbl">
        <thead>
          <tr>
            <th>SO number</th>
            <th>Order date</th>
            <th>Status</th>
            <th className="right">Total</th>
          </tr>
        </thead>
        <tbody>
          {orders.map((so) => (
            <tr key={so.id}>
              <td className="mono">{so.so_number}</td>
              <td className="muted">{formatDate(so.order_date)}</td>
              <td>
                <Badge variant={so.status === SalesOrderStatus.SHIPPED ? 'success' : 'ink'} dot>
                  {so.status}
                </Badge>
              </td>
              <td className="right mono">{formatCurrency(so.total)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
