import { useEffect, useMemo, useState } from 'react';

import { PageError } from '@/components/errors/PageError';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Pager } from '@/components/ui/Pager';
import { useItemsList } from '@/features/items/hooks/useItems';
import type { Item } from '@/types/api.types';
import type { MovementDirection, MovementReason } from '@/types/enums';

import { ManualAdjustmentModal } from '../components/ManualAdjustmentModal';
import { StockMovementsTable } from '../components/StockMovementsTable';
import {
  StockMovementsToolbar,
  type DirectionFilter,
  type ReasonFilter,
} from '../components/StockMovementsToolbar';
import { useStockMovements } from '../hooks/useStockMovements';

const DEFAULT_LIMIT = 25;

export function StockMovementsListPage(): JSX.Element {
  const [itemId, setItemId] = useState('');
  const [direction, setDirection] = useState<DirectionFilter>('ALL');
  const [reason, setReason] = useState<ReasonFilter>('ALL');
  const [limit, setLimit] = useState(DEFAULT_LIMIT);
  const [offset, setOffset] = useState(0);
  const [adjustOpen, setAdjustOpen] = useState(false);

  useEffect(() => {
    setOffset(0);
  }, [itemId, direction, reason, limit]);

  const itemsQuery = useItemsList({ limit: 100, offset: 0 });
  const itemMap = useMemo(() => {
    const map = new Map<string, Item>();
    for (const item of itemsQuery.data?.items ?? []) map.set(item.id, item);
    return map;
  }, [itemsQuery.data]);

  const query = useStockMovements({
    limit,
    offset,
    item_id: itemId || undefined,
    direction: direction === 'ALL' ? undefined : (direction as MovementDirection),
    reason: reason === 'ALL' ? undefined : (reason as MovementReason),
  });

  return (
    <>
      <PageHeader
        title="Stock Movements"
        sub="The append-only audit ledger — every quantity change, traceable"
        actions={
          <>
            {/* Export is a Phase-2 placeholder (UI_SPEC §6.8). */}
            <button className="btn btn-sec" type="button" disabled title="Coming soon">
              Export CSV
            </button>
            <Button variant="pri" icon="plus" onClick={() => setAdjustOpen(true)}>
              Manual Adjustment
            </Button>
          </>
        }
      />

      {query.isError && !query.data ? (
        <PageError error={query.error} onRetry={() => void query.refetch()} />
      ) : (
        <Card>
          <StockMovementsToolbar
            itemId={itemId}
            onItem={setItemId}
            items={itemsQuery.data?.items ?? []}
            direction={direction}
            onDirection={setDirection}
            reason={reason}
            onReason={setReason}
          />
          <StockMovementsTable
            movements={query.data?.items ?? []}
            loading={query.isPending}
            itemName={(id) => itemMap.get(id)?.name ?? '—'}
            onAdjust={() => setAdjustOpen(true)}
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

      {adjustOpen && <ManualAdjustmentModal onClose={() => setAdjustOpen(false)} />}
    </>
  );
}
