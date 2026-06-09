import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { routes } from '@/app/routes';
import { PageError } from '@/components/errors/PageError';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Pager } from '@/components/ui/Pager';
import { useDebounce } from '@/hooks/useDebounce';
import type { Vendor } from '@/types/api.types';

import { VendorFormDrawer } from '../components/VendorFormDrawer';
import { VendorsTable } from '../components/VendorsTable';
import { VendorsToolbar } from '../components/VendorsToolbar';
import { useVendorsList } from '../hooks/useVendors';

const DEFAULT_LIMIT = 25;

export function VendorsListPage(): JSX.Element {
  const navigate = useNavigate();
  const [searchInput, setSearchInput] = useState('');
  const search = useDebounce(searchInput, 300);
  const [limit, setLimit] = useState(DEFAULT_LIMIT);
  const [offset, setOffset] = useState(0);

  const [createOpen, setCreateOpen] = useState(false);
  const [editVendor, setEditVendor] = useState<Vendor | null>(null);

  useEffect(() => {
    setOffset(0);
  }, [search, limit]);

  const query = useVendorsList({ limit, offset, search });

  return (
    <>
      <PageHeader
        title="Vendors"
        sub="Who you buy from, and the items they supply"
        actions={
          <Button variant="pri" icon="plus" onClick={() => setCreateOpen(true)}>
            Add Vendor
          </Button>
        }
      />

      {query.isError && !query.data ? (
        <PageError error={query.error} onRetry={() => void query.refetch()} />
      ) : (
        <Card>
          <VendorsToolbar search={searchInput} onSearch={setSearchInput} />
          <VendorsTable
            vendors={query.data?.items ?? []}
            loading={query.isPending}
            onEdit={setEditVendor}
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
        <VendorFormDrawer
          mode="create"
          onClose={() => setCreateOpen(false)}
          onCreated={(id) => navigate(`${routes.vendors}/${id}`)}
        />
      )}
      {editVendor && (
        <VendorFormDrawer mode="edit" vendor={editVendor} onClose={() => setEditVendor(null)} />
      )}
    </>
  );
}
