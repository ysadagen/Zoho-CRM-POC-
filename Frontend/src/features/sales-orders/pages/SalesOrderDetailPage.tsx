import { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { routes } from '@/app/routes';
import { PageError } from '@/components/errors/PageError';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button, ButtonLink } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import { useCustomersList } from '@/features/customers/hooks/useCustomers';
import { useItemsList } from '@/features/items/hooks/useItems';
import { formatCurrency, formatDate } from '@/lib/format';
import type { Item } from '@/types/api.types';
import { SalesOrderStatus } from '@/types/enums';

import { ShipSoModal } from '../components/ShipSoModal';
import { SoStatusBadge } from '../components/SoStatusBadge';
import { useSalesOrder } from '../hooks/useSalesOrders';

export function SalesOrderDetailPage(): JSX.Element {
  const { id = '' } = useParams();
  const soQuery = useSalesOrder(id);
  const customersQuery = useCustomersList({ limit: 100, offset: 0 });
  const itemsQuery = useItemsList({ limit: 100, offset: 0 });
  const [shipOpen, setShipOpen] = useState(false);

  const itemMap = useMemo(() => {
    const map = new Map<string, Item>();
    for (const item of itemsQuery.data?.items ?? []) map.set(item.id, item);
    return map;
  }, [itemsQuery.data]);

  if (soQuery.isPending) {
    return (
      <>
        <div className="page-head">
          <Skeleton width={240} height={30} />
        </div>
        <Card pad>
          <Skeleton height={160} />
        </Card>
      </>
    );
  }
  if (soQuery.isError || !soQuery.data) {
    return <PageError error={soQuery.error} onRetry={() => void soQuery.refetch()} />;
  }

  const so = soQuery.data;
  const customer = customersQuery.data?.items.find((c) => c.id === so.customer_id);
  const isDraft = so.status === SalesOrderStatus.DRAFT;

  return (
    <>
      <PageHeader
        title={<span className="mono">{so.so_number}</span>}
        sub={
          <span className="flex items-center gap-8">
            {customer ? (
              <Link className="tbl-link" to={`${routes.customers}/${customer.id}`}>
                {customer.company_name}
              </Link>
            ) : (
              '—'
            )}
            <SoStatusBadge status={so.status} />
          </span>
        }
        actions={
          <>
            <ButtonLink to={routes.salesOrders} variant="sec">
              ← Sales Orders
            </ButtonLink>
            {isDraft && (
              <Button variant="pri" onClick={() => setShipOpen(true)}>
                Ship
              </Button>
            )}
          </>
        }
      />

      <div className="stat-grid">
        <div className="stat">
          <div className="l">Order date</div>
          <div className="v">{formatDate(so.order_date)}</div>
        </div>
        <div className="stat">
          <div className="l">Expected delivery</div>
          <div className="v">{so.expected_delivery_date ? formatDate(so.expected_delivery_date) : '—'}</div>
        </div>
        <div className="stat">
          <div className="l">Shipped</div>
          <div className="v">{so.shipped_date ? formatDate(so.shipped_date) : '—'}</div>
        </div>
        <div className="stat">
          <div className="l">Total</div>
          <div className="v mono">{formatCurrency(so.total)}</div>
        </div>
      </div>

      <Card className="tbl-wrap">
        <table className="tbl">
          <thead>
            <tr>
              <th>Item</th>
              <th className="right">Qty</th>
              <th className="right">Unit price</th>
              <th className="right">Line total</th>
            </tr>
          </thead>
          <tbody>
            {so.items.map((line) => (
              <tr key={line.id}>
                <td>{itemMap.get(line.item_id)?.name ?? line.item_id}</td>
                <td className="right mono">{line.quantity}</td>
                <td className="right mono">{formatCurrency(line.unit_price)}</td>
                <td className="right mono">{formatCurrency(line.line_total)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      {so.notes && (
        <Card pad className="mt-16">
          <div className="eyebrow mb-8">Notes</div>
          <div className="text-ink">{so.notes}</div>
        </Card>
      )}

      <div className="text-muted fs-12 mt-16">
        Created {formatDate(so.created_at)} · Last updated {formatDate(so.updated_at)}
        {isDraft ? '' : ' · Stock impact recorded in the audit ledger'}
      </div>

      {shipOpen && <ShipSoModal so={so} onClose={() => setShipOpen(false)} />}
    </>
  );
}
