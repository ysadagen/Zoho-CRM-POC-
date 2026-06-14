import { Link } from 'react-router-dom';

import { routes } from '@/app/routes';
import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { Skeleton } from '@/components/ui/Skeleton';
import { formatCurrency, formatDate } from '@/lib/format';
import type { PurchaseOrder } from '@/types/api.types';
import { PurchaseOrderStatus } from '@/types/enums';

import { PoStatusBadge } from './PoStatusBadge';

const COL_COUNT = 8;
const SKELETON_ROWS = ['a', 'b', 'c', 'd', 'e'];

export interface PurchaseOrdersTableProps {
  orders: PurchaseOrder[];
  loading: boolean;
  vendorName: (vendorId: string) => string;
  onReceive: (po: PurchaseOrder) => void;
  onCreate: () => void;
}

export function PurchaseOrdersTable({
  orders,
  loading,
  vendorName,
  onReceive,
  onCreate,
}: PurchaseOrdersTableProps): JSX.Element {
  return (
    <div className="tbl-wrap">
      <table className="tbl">
        <thead>
          <tr>
            <th>PO number</th>
            <th>Vendor</th>
            <th>Order date</th>
            <th>Expected</th>
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
              <td colSpan={COL_COUNT + 1}>
                <EmptyState
                  icon="cart"
                  title="No purchase orders"
                  sub="Raise your first purchase order to stock up on raw materials."
                  action={
                    <Button variant="pri" icon="plus" onClick={onCreate}>
                      New Purchase Order
                    </Button>
                  }
                />
              </td>
            </tr>
          ) : (
            orders.map((po) => (
              <tr key={po.id}>
                <td>
                  <Link className="tbl-link mono" to={`${routes.purchaseOrders}/${po.id}`}>
                    {po.po_number}
                  </Link>
                </td>
                <td className="muted">{vendorName(po.vendor_id)}</td>
                <td className="muted">{formatDate(po.order_date)}</td>
                <td className="muted">
                  {po.expected_delivery_date ? formatDate(po.expected_delivery_date) : '—'}
                </td>
                <td>
                  <PoStatusBadge status={po.status} />
                </td>
                <td className="right mono">{po.items.length}</td>
                <td className="right mono">{formatCurrency(po.total)}</td>
                <td className="right">
                  <Link className="btn btn-txt btn-sm" to={`${routes.purchaseOrders}/${po.id}`}>
                    View
                  </Link>
                  {po.status === PurchaseOrderStatus.DRAFT && (
                    <button className="btn btn-txt btn-sm" type="button" onClick={() => onReceive(po)}>
                      Receive
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
