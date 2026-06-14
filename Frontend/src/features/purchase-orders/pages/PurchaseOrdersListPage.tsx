import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { routes } from '@/app/routes';
import { PageError } from '@/components/errors/PageError';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Pager } from '@/components/ui/Pager';
import { useVendorsList } from '@/features/vendors/hooks/useVendors';
import type { PurchaseOrder, Vendor } from '@/types/api.types';
import type { PurchaseOrderStatus } from '@/types/enums';

import { PurchaseOrdersTable } from '../components/PurchaseOrdersTable';
import { PurchaseOrdersToolbar, type PoStatusFilter } from '../components/PurchaseOrdersToolbar';
import { ReceivePoModal } from '../components/ReceivePoModal';
import { usePurchaseOrdersList } from '../hooks/usePurchaseOrders';

const DEFAULT_LIMIT = 25;

export function PurchaseOrdersListPage(): JSX.Element {
  const navigate = useNavigate();
  const [status, setStatus] = useState<PoStatusFilter>('ALL');
  const [vendorId, setVendorId] = useState('');
  const [limit, setLimit] = useState(DEFAULT_LIMIT);
  const [offset, setOffset] = useState(0);
  const [receivePo, setReceivePo] = useState<PurchaseOrder | null>(null);

  useEffect(() => {
    setOffset(0);
  }, [status, vendorId, limit]);

  const vendorsQuery = useVendorsList({ limit: 100, offset: 0 });
  const vendorMap = useMemo(() => {
    const map = new Map<string, Vendor>();
    for (const vendor of vendorsQuery.data?.items ?? []) map.set(vendor.id, vendor);
    return map;
  }, [vendorsQuery.data]);

  const query = usePurchaseOrdersList({
    limit,
    offset,
    status: status === 'ALL' ? undefined : (status as PurchaseOrderStatus),
    vendor_id: vendorId || undefined,
  });

  return (
    <>
      <PageHeader
        title="Purchase Orders"
        sub="Buying raw materials from vendors"
        actions={
          <Button variant="pri" icon="plus" onClick={() => navigate(`${routes.purchaseOrders}/new`)}>
            New Purchase Order
          </Button>
        }
      />

      {query.isError && !query.data ? (
        <PageError error={query.error} onRetry={() => void query.refetch()} />
      ) : (
        <Card>
          <PurchaseOrdersToolbar
            status={status}
            onStatus={setStatus}
            vendorId={vendorId}
            onVendor={setVendorId}
            vendors={vendorsQuery.data?.items ?? []}
          />
          <PurchaseOrdersTable
            orders={query.data?.items ?? []}
            loading={query.isPending}
            vendorName={(id) => vendorMap.get(id)?.vendor_name ?? '—'}
            onReceive={setReceivePo}
            onCreate={() => navigate(`${routes.purchaseOrders}/new`)}
          />
          {query.data && query.data.total > 0 && (
            <Pager
              total={query.data.total}
              limit={limit}
              offset={offset}
              onChange={({ limit: nextLimit, offset: nextOffset }) => {
                setLimit(nextLimit);
                setOffset(nextOffset);
              }}
            />
          )}
        </Card>
      )}

      {receivePo && <ReceivePoModal po={receivePo} onClose={() => setReceivePo(null)} />}
    </>
  );
}
