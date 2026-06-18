import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

import { routes } from '@/app/routes';
import { PageError } from '@/components/errors/PageError';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Pager } from '@/components/ui/Pager';
import { useDebounce } from '@/hooks/useDebounce';
import type { Item } from '@/types/api.types';
import type { ItemType } from '@/types/enums';

import { ItemFormDrawer } from '../components/ItemFormDrawer';
import { ItemsTable } from '../components/ItemsTable';
import { ItemsToolbar, type StatusFilter, type TypeFilter } from '../components/ItemsToolbar';
import { useItemsList } from '../hooks/useItems';
import { STATUS_FILTER_TO_STATUSES } from '../item.transform';

const DEFAULT_LIMIT = 25;

export function ItemsListPage(): JSX.Element {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [searchInput, setSearchInput] = useState('');
  const search = useDebounce(searchInput, 300);
  const [type, setType] = useState<TypeFilter>('ALL');
  const [status, setStatus] = useState<StatusFilter>(() => {
    const s = searchParams.get('status');
    return s === 'ok' || s === 'low' || s === 'out' || s === 'attention' ? s : 'all';
  });
  const [includeInactive, setIncludeInactive] = useState(false);
  const [limit, setLimit] = useState(DEFAULT_LIMIT);
  const [offset, setOffset] = useState(0);

  // Quick Actions deep-link here with `?new=1` to open the create drawer.
  const [createOpen, setCreateOpen] = useState(() => searchParams.get('new') === '1');
  const [editItem, setEditItem] = useState<Item | null>(null);

  const closeCreate = (): void => {
    setCreateOpen(false);
    if (searchParams.has('new')) {
      searchParams.delete('new');
      setSearchParams(searchParams, { replace: true });
    }
  };

  // A changed server-side filter invalidates the current page position.
  useEffect(() => {
    setOffset(0);
  }, [search, type, status, includeInactive, limit]);

  const query = useItemsList({
    limit,
    offset,
    type: type === 'ALL' ? undefined : (type as ItemType),
    search,
    // Status is a real server filter, so the result + pager total are correct
    // across the whole catalog (not just the loaded page).
    statuses: status === 'all' ? undefined : STATUS_FILTER_TO_STATUSES[status],
    includeInactive,
  });

  const rows = query.data?.items ?? [];

  return (
    <>
      <PageHeader
        title="Items"
        sub="Raw materials and finished products"
        actions={
          <Button variant="pri" icon="plus" onClick={() => setCreateOpen(true)}>
            Add Item
          </Button>
        }
      />

      {query.isError && !query.data ? (
        <PageError error={query.error} onRetry={() => void query.refetch()} />
      ) : (
        <Card>
          <ItemsToolbar
            search={searchInput}
            onSearch={setSearchInput}
            type={type}
            onType={setType}
            status={status}
            onStatus={setStatus}
            includeInactive={includeInactive}
            onIncludeInactive={setIncludeInactive}
          />
          <ItemsTable
            items={rows}
            loading={query.isPending}
            onEdit={setEditItem}
            onAddItem={() => setCreateOpen(true)}
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
        <ItemFormDrawer
          mode="create"
          onClose={closeCreate}
          onCreated={(id) => navigate(`${routes.items}/${id}`)}
        />
      )}
      {editItem && (
        <ItemFormDrawer mode="edit" item={editItem} onClose={() => setEditItem(null)} />
      )}
    </>
  );
}
