import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { routes } from '@/app/routes';
import { PageError } from '@/components/errors/PageError';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Pager } from '@/components/ui/Pager';
import { useCustomersList } from '@/features/customers/hooks/useCustomers';
import type { Customer, SalesOrder } from '@/types/api.types';
import type { SalesOrderStatus } from '@/types/enums';

import { SalesOrdersTable } from '../components/SalesOrdersTable';
import { SalesOrdersToolbar, type SoStatusFilter } from '../components/SalesOrdersToolbar';
import { ShipSoModal } from '../components/ShipSoModal';
import { useSalesOrdersList } from '../hooks/useSalesOrders';

const DEFAULT_LIMIT = 25;

export function SalesOrdersListPage(): JSX.Element {
  const navigate = useNavigate();
  const [status, setStatus] = useState<SoStatusFilter>('ALL');
  const [customerId, setCustomerId] = useState('');
  const [limit, setLimit] = useState(DEFAULT_LIMIT);
  const [offset, setOffset] = useState(0);
  const [shipSo, setShipSo] = useState<SalesOrder | null>(null);

  useEffect(() => {
    setOffset(0);
  }, [status, customerId, limit]);

  const customersQuery = useCustomersList({ limit: 100, offset: 0 });
  const customerMap = useMemo(() => {
    const map = new Map<string, Customer>();
    for (const customer of customersQuery.data?.items ?? []) map.set(customer.id, customer);
    return map;
  }, [customersQuery.data]);

  const query = useSalesOrdersList({
    limit,
    offset,
    // `status` only holds a fixed filter option; 'ALL' maps to no filter, so
    // the cast narrows the remaining string to the query enum.
    status: status === 'ALL' ? undefined : (status as SalesOrderStatus),
    customer_id: customerId || undefined,
  });

  return (
    <>
      <PageHeader
        title="Sales Orders"
        sub="Fulfilling customer demand from finished-goods stock"
        actions={
          <Button variant="pri" icon="plus" onClick={() => navigate(`${routes.salesOrders}/new`)}>
            New Sales Order
          </Button>
        }
      />

      {query.isError && !query.data ? (
        <PageError error={query.error} onRetry={() => void query.refetch()} />
      ) : (
        <Card>
          <SalesOrdersToolbar
            status={status}
            onStatus={setStatus}
            customerId={customerId}
            onCustomer={setCustomerId}
            customers={customersQuery.data?.items ?? []}
          />
          <SalesOrdersTable
            orders={query.data?.items ?? []}
            loading={query.isPending}
            customerName={(id) => customerMap.get(id)?.company_name ?? '—'}
            onShip={setShipSo}
            onCreate={() => navigate(`${routes.salesOrders}/new`)}
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

      {shipSo && <ShipSoModal so={shipSo} onClose={() => setShipSo(null)} />}
    </>
  );
}
