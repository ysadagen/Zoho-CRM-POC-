import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

import { routes } from '@/app/routes';
import { PageError } from '@/components/errors/PageError';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Pager } from '@/components/ui/Pager';
import { useDebounce } from '@/hooks/useDebounce';
import type { Customer } from '@/types/api.types';

import { CustomerFormDrawer } from '../components/CustomerFormDrawer';
import { CustomersTable } from '../components/CustomersTable';
import { CustomersToolbar } from '../components/CustomersToolbar';
import { useCustomersList } from '../hooks/useCustomers';

const DEFAULT_LIMIT = 25;

export function CustomersListPage(): JSX.Element {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [searchInput, setSearchInput] = useState('');
  const search = useDebounce(searchInput, 300);
  const [limit, setLimit] = useState(DEFAULT_LIMIT);
  const [offset, setOffset] = useState(0);

  // Quick Actions deep-link here with `?new=1` to open the create drawer.
  const [createOpen, setCreateOpen] = useState(() => searchParams.get('new') === '1');
  const [editCustomer, setEditCustomer] = useState<Customer | null>(null);

  const closeCreate = (): void => {
    setCreateOpen(false);
    if (searchParams.has('new')) {
      searchParams.delete('new');
      setSearchParams(searchParams, { replace: true });
    }
  };

  useEffect(() => {
    setOffset(0);
  }, [search, limit]);

  const query = useCustomersList({ limit, offset, search });

  return (
    <>
      <PageHeader
        title="Customers"
        sub="Who you sell to — relationship history lives in Zoho CRM"
        actions={
          <Button variant="pri" icon="plus" onClick={() => setCreateOpen(true)}>
            Add Customer
          </Button>
        }
      />

      {query.isError && !query.data ? (
        <PageError error={query.error} onRetry={() => void query.refetch()} />
      ) : (
        <Card>
          <CustomersToolbar search={searchInput} onSearch={setSearchInput} />
          <CustomersTable
            customers={query.data?.items ?? []}
            loading={query.isPending}
            onEdit={setEditCustomer}
            onAdd={() => setCreateOpen(true)}
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

      {createOpen && (
        <CustomerFormDrawer
          mode="create"
          onClose={closeCreate}
          onCreated={(id) => navigate(`${routes.customers}/${id}`)}
        />
      )}
      {editCustomer && (
        <CustomerFormDrawer
          mode="edit"
          customer={editCustomer}
          onClose={() => setEditCustomer(null)}
        />
      )}
    </>
  );
}
