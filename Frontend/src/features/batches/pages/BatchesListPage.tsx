import { useEffect, useMemo, useState } from 'react';

import { PageError } from '@/components/errors/PageError';
import { PageHeader } from '@/components/layout/PageHeader';
import { useToast } from '@/components/toast/useToast';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Pager } from '@/components/ui/Pager';
import { useItemsList } from '@/features/items/hooks/useItems';
import { useApiError } from '@/hooks/useApiError';
import type { Batch, Item } from '@/types/api.types';
import { BatchStatus } from '@/types/enums';

import { BatchFormDrawer } from '../components/BatchFormDrawer';
import { BatchesTable } from '../components/BatchesTable';
import { BatchesToolbar, type StatusFilter } from '../components/BatchesToolbar';
import { useBatchesList, useChangeBatchStatus } from '../hooks/useBatches';

const STATUS_VERB: Record<string, string> = {
  [BatchStatus.RELEASED]: 'released',
  [BatchStatus.REJECTED]: 'rejected',
  [BatchStatus.RECALLED]: 'recalled',
};

const DEFAULT_LIMIT = 25;

export function BatchesListPage(): JSX.Element {
  const [itemId, setItemId] = useState('');
  const [status, setStatus] = useState<StatusFilter>('');
  const [expiringBefore, setExpiringBefore] = useState('');
  const [limit, setLimit] = useState(DEFAULT_LIMIT);
  const [offset, setOffset] = useState(0);
  const [createOpen, setCreateOpen] = useState(false);

  // A changed filter invalidates the current page position.
  useEffect(() => {
    setOffset(0);
  }, [itemId, status, expiringBefore, limit]);

  const itemsQuery = useItemsList({ limit: 100, offset: 0 });
  const itemMap = useMemo(() => {
    const map = new Map<string, Item>();
    for (const item of itemsQuery.data?.items ?? []) map.set(item.id, item);
    return map;
  }, [itemsQuery.data]);

  const query = useBatchesList({
    limit,
    offset,
    item_id: itemId || undefined,
    // `status` only holds a fixed filter option; '' maps to no filter, so the
    // cast narrows the remaining string to the query enum.
    status: status === '' ? undefined : (status as BatchStatus),
    expiring_before: expiringBefore || undefined,
  });

  const toast = useToast();
  const reportApiError = useApiError();
  const statusMut = useChangeBatchStatus();

  const onChangeStatus = (batch: Batch, next: BatchStatus): void => {
    statusMut.mutate(
      { id: batch.id, status: next },
      {
        onSuccess: (updated) =>
          toast.success(`Lot ${updated.batch_number} ${STATUS_VERB[next] ?? 'updated'}.`),
        onError: (error) => reportApiError(error, { scope: 'batches.status' }),
      },
    );
  };

  return (
    <>
      <PageHeader
        title="Batches"
        sub="Lots in stock — expiry, QC status and traceability"
        actions={
          <Button variant="pri" icon="plus" onClick={() => setCreateOpen(true)}>
            New Lot
          </Button>
        }
      />

      {query.isError && !query.data ? (
        <PageError error={query.error} onRetry={() => void query.refetch()} />
      ) : (
        <Card>
          <BatchesToolbar
            itemId={itemId}
            onItem={setItemId}
            items={itemsQuery.data?.items ?? []}
            status={status}
            onStatus={setStatus}
            expiringBefore={expiringBefore}
            onExpiringBefore={setExpiringBefore}
          />
          <BatchesTable
            batches={query.data?.items ?? []}
            loading={query.isPending}
            itemName={(id) => itemMap.get(id)?.name ?? '—'}
            onAdd={() => setCreateOpen(true)}
            onChangeStatus={onChangeStatus}
            busyId={statusMut.isPending ? statusMut.variables?.id : null}
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

      {createOpen && <BatchFormDrawer onClose={() => setCreateOpen(false)} />}
    </>
  );
}
