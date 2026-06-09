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
import { STATUS_FILTER_TO_STATUS } from '../item.transform';

const DEFAULT_LIMIT = 25;

export function ItemsListPage(): JSX.Element {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [searchInput, setSearchInput] = useState('');
  const search = useDebounce(searchInput, 300);
  const [type, setType] = useState<TypeFilter>('ALL');
  const [status, setStatus] = useState<StatusFilter>(() => {
    const s = searchParams.get('status');
    return s === 'ok' || s === 'low' || s === 'out' ? s : 'all';
  });
  const [limit, setLimit] = useState(DEFAULT_LIMIT);
  const [offset, setOffset] = useState(0);

  const [createOpen, setCreateOpen] = useState(false);
  const [editItem, setEditItem] = useState<Item | null>(null);

  // A changed server-side filter invalidates the current page position.
  useEffect(() => {
    setOffset(0);
  }, [search, type, limit]);

  const query = useItemsList({
    limit,
    offset,
    type: type === 'ALL' ? undefined : (type as ItemType),
    search,
  });

  // Status has no Backend filter (Backend §9.3), so it filters the loaded page.
  const pageRows = query.data?.items ?? [];
  const rows =
    status === 'all'
      ? pageRows
      : pageRows.filter((item) => item.status === STATUS_FILTER_TO_STATUS[status]);

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
          onClose={() => setCreateOpen(false)}
          onCreated={(id) => navigate(`${routes.items}/${id}`)}
        />
      )}
      {editItem && (
        <ItemFormDrawer mode="edit" item={editItem} onClose={() => setEditItem(null)} />
      )}
    </>
  );
}
