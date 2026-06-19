import { useEffect, useMemo, useState } from 'react';

import { PageError } from '@/components/errors/PageError';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Pager } from '@/components/ui/Pager';
import { useBatchesList } from '@/features/batches/hooks/useBatches';
import { useCustomersList } from '@/features/customers/hooks/useCustomers';
import { useItemsList } from '@/features/items/hooks/useItems';
import { usePurchaseOrdersList } from '@/features/purchase-orders/hooks/usePurchaseOrders';
import { useSalesOrdersList } from '@/features/sales-orders/hooks/useSalesOrders';
import { useVendorsList } from '@/features/vendors/hooks/useVendors';
import type { Batch, Customer, Item, PurchaseOrder, SalesOrder, Vendor } from '@/types/api.types';
import type { MovementDirection, MovementReason } from '@/types/enums';

import { ManualAdjustmentModal } from '../components/ManualAdjustmentModal';
import { StockMovementsTable } from '../components/StockMovementsTable';
import {
  StockMovementsToolbar,
  type DirectionFilter,
  type ReasonFilter,
} from '../components/StockMovementsToolbar';
import { useStockMovements } from '../hooks/useStockMovements';
import { movementParty, type PartyMaps } from '../sm.transform';

/** Build an id→entity map from a paginated list result. */
function byId<T extends { id: string }>(rows: T[] | undefined): Map<string, T> {
  return new Map((rows ?? []).map((row) => [row.id, row]));
}

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

  // Resolve each movement's reference to a customer/vendor. The ledger only
  // carries reference_type + reference_id, so we join POs→vendors / SOs→customers
  // client-side. Mirrors the items query (first 100 of each).
  const poQuery = usePurchaseOrdersList({ limit: 100, offset: 0 });
  const soQuery = useSalesOrdersList({ limit: 100, offset: 0 });
  const vendorsQuery = useVendorsList({ limit: 100, offset: 0 });
  const customersQuery = useCustomersList({ limit: 100, offset: 0 });

  // Resolve a movement's batch_id → batch number for the Lot column (first 100,
  // mirroring the other lookups). PO receive / SO ship set batch_id; manual
  // adjustments leave it null.
  const batchesQuery = useBatchesList({ limit: 100, offset: 0 });
  const batchMap = useMemo(() => byId<Batch>(batchesQuery.data?.items), [batchesQuery.data]);
  const lot = (m: { batch_id: string | null }): string =>
    m.batch_id ? (batchMap.get(m.batch_id)?.batch_number ?? '—') : '—';

  const partyMaps = useMemo<PartyMaps>(
    () => ({
      purchaseOrders: byId<PurchaseOrder>(poQuery.data?.items),
      salesOrders: byId<SalesOrder>(soQuery.data?.items),
      vendors: byId<Vendor>(vendorsQuery.data?.items),
      customers: byId<Customer>(customersQuery.data?.items),
    }),
    [poQuery.data, soQuery.data, vendorsQuery.data, customersQuery.data],
  );

  const query = useStockMovements({
    limit,
    offset,
    item_id: itemId || undefined,
    // direction/reason only hold a fixed filter option; 'ALL' maps to no
    // filter, so each cast narrows the remaining string to its query enum.
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
            party={(m) => movementParty(m, partyMaps)}
            lot={lot}
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
