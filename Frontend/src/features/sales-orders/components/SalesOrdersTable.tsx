import { Link } from 'react-router-dom';

import { routes } from '@/app/routes';
import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { Skeleton } from '@/components/ui/Skeleton';
import { formatCurrency, formatDate } from '@/lib/format';
import type { SalesOrder } from '@/types/api.types';
import { SalesOrderStatus } from '@/types/enums';

import { SoStatusBadge } from './SoStatusBadge';

const COL_COUNT = 7;
const SKELETON_ROWS = ['a', 'b', 'c', 'd', 'e'];

export interface SalesOrdersTableProps {
  orders: SalesOrder[];
  loading: boolean;
  customerName: (customerId: string) => string;
  onShip: (so: SalesOrder) => void;
  onCreate: () => void;
}

export function SalesOrdersTable({
  orders,
  loading,
  customerName,
  onShip,
  onCreate,
}: SalesOrdersTableProps): JSX.Element {
  return (
    <div className="tbl-wrap">
      <table className="tbl">
        <thead>
          <tr>
            <th>SO number</th>
            <th>Customer</th>
            <th>Order date</th>
            <th>Status</th>
            <th className="right">Items</th>
            <th className="right">Total</th>
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
          ) : orders.length === 0 ? (
            <tr>
              <td colSpan={COL_COUNT}>
                <EmptyState
                  icon="bag"
                  title="No sales orders"
                  sub="Create your first sales order to fulfil customer demand."
                  action={
                    <Button variant="pri" icon="plus" onClick={onCreate}>
                      New Sales Order
                    </Button>
                  }
                />
              </td>
            </tr>
          ) : (
            orders.map((so) => (
              <tr key={so.id}>
                <td>
                  <Link className="tbl-link mono" to={`${routes.salesOrders}/${so.id}`}>
                    {so.so_number}
                  </Link>
                </td>
                <td className="muted">{customerName(so.customer_id)}</td>
                <td className="muted">{formatDate(so.order_date)}</td>
                <td>
                  <SoStatusBadge status={so.status} />
                </td>
                <td className="right mono">{so.items.length}</td>
                <td className="right mono">{formatCurrency(so.total)}</td>
                <td className="right">
                  <Link className="btn btn-txt btn-sm" to={`${routes.salesOrders}/${so.id}`}>
                    View
                  </Link>
                  {so.status === SalesOrderStatus.DRAFT && (
                    <button className="btn btn-txt btn-sm" type="button" onClick={() => onShip(so)}>
                      Ship
                    </button>
                  )}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
