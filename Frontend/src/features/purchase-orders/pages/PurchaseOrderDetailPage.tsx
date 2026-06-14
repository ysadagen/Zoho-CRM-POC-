import { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { routes } from '@/app/routes';
import { PageError } from '@/components/errors/PageError';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button, ButtonLink } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import { useItemsList } from '@/features/items/hooks/useItems';
import { useVendorsList } from '@/features/vendors/hooks/useVendors';
import { formatCurrency, formatDate } from '@/lib/format';
import type { Item } from '@/types/api.types';
import { PurchaseOrderStatus } from '@/types/enums';

import { PoStatusBadge } from '../components/PoStatusBadge';
import { ReceivePoModal } from '../components/ReceivePoModal';
import { usePurchaseOrder } from '../hooks/usePurchaseOrders';

export function PurchaseOrderDetailPage(): JSX.Element {
  const { id = '' } = useParams();
  const poQuery = usePurchaseOrder(id);
  const vendorsQuery = useVendorsList({ limit: 100, offset: 0 });
  const itemsQuery = useItemsList({ limit: 100, offset: 0 });
  const [receiveOpen, setReceiveOpen] = useState(false);

  const itemMap = useMemo(() => {
    const map = new Map<string, Item>();
    for (const item of itemsQuery.data?.items ?? []) map.set(item.id, item);
    return map;
  }, [itemsQuery.data]);

  if (poQuery.isPending) {
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
  if (poQuery.isError || !poQuery.data) {
    return <PageError error={poQuery.error} onRetry={() => void poQuery.refetch()} />;
  }

  const po = poQuery.data;
  const vendor = vendorsQuery.data?.items.find((v) => v.id === po.vendor_id);
  const isDraft = po.status === PurchaseOrderStatus.DRAFT;

  return (
    <>
      <PageHeader
        title={<span className="mono">{po.po_number}</span>}
        sub={
          <span className="flex items-center gap-8">
            {vendor ? (
              <Link className="tbl-link" to={`${routes.vendors}/${vendor.id}`}>
                {vendor.vendor_name}
              </Link>
            ) : (
              '—'
            )}
            <PoStatusBadge status={po.status} />
          </span>
        }
        actions={
          <>
            <ButtonLink to={routes.purchaseOrders} variant="sec">
              ← Purchase Orders
            </ButtonLink>
            {isDraft && (
              <Button variant="pri" onClick={() => setReceiveOpen(true)}>
                Receive
              </Button>
            )}
          </>
        }
      />

      <div className="stat-grid">
        <div className="stat">
          <div className="l">Order date</div>
          <div className="v">{formatDate(po.order_date)}</div>
        </div>
        <div className="stat">
          <div className="l">Expected delivery</div>
          <div className="v">{po.expected_delivery_date ? formatDate(po.expected_delivery_date) : '—'}</div>
        </div>
        <div className="stat">
          <div className="l">Received</div>
          <div className="v">{po.received_date ? formatDate(po.received_date) : '—'}</div>
        </div>
        <div className="stat">
          <div className="l">Total</div>
          <div className="v mono">{formatCurrency(po.total)}</div>
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
            {po.items.map((line) => (
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

      {po.notes && (
        <Card pad className="mt-16">
          <div className="eyebrow mb-8">Notes</div>
          <div className="text-ink">{po.notes}</div>
        </Card>
      )}

      <div className="text-muted fs-12 mt-16">
        Created {formatDate(po.created_at)} · Last updated {formatDate(po.updated_at)}
        {isDraft ? '' : ' · Stock impact recorded in the audit ledger'}
      </div>

      {receiveOpen && <ReceivePoModal po={po} onClose={() => setReceiveOpen(false)} />}
    </>
  );
}
