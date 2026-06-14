import { useState } from 'react';
import { useLocation, useParams } from 'react-router-dom';

import { routes } from '@/app/routes';
import { PageError } from '@/components/errors/PageError';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button, ButtonLink } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import { Tabs } from '@/components/ui/Tabs';
import { formatCurrency, formatDate, formatQuantity, formatRelative } from '@/lib/format';
import type { Item } from '@/types/api.types';

import { ItemStatusBadge, ItemTypeBadge } from '../components/ItemBadges';
import { ItemFormDrawer } from '../components/ItemFormDrawer';
import { ItemMovementsTab } from '../components/ItemMovementsTab';
import { useItem, useItemMovements } from '../hooks/useItems';
import { summariseMovements } from '../item.transform';
import '../items.css';

type DetailTab = 'overview' | 'history';

const TABS = [
  { value: 'overview', label: 'Overview' },
  { value: 'history', label: 'Movement history' },
] as const;

function Stat({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="stat">
      <div className="l">{label}</div>
      <div className="v mono">{value}</div>
    </div>
  );
}

function Overview({ item }: { item: Item }): JSX.Element {
  const unit = item.unit_of_measure;
  return (
    <Card pad>
      <div className="item-overview">
        <Detail label="SKU" value={item.sku} mono />
        <Detail label="Name" value={item.name} />
        <Detail label="Unit of measure" value={unit} />
        <Detail label="Default unit price" value={formatCurrency(item.unit_price)} />
        <Detail
          label="Reorder threshold"
          value={item.reorder_threshold ? formatQuantity(item.reorder_threshold, unit) : '—'}
        />
        <Detail label="Current stock" value={formatQuantity(item.stock_quantity, unit)} />
        <div className="full">
          <Detail label="Description" value={item.description ?? '—'} />
        </div>
        <Detail label="Created" value={formatDate(item.created_at)} />
        <Detail label="Last updated" value={formatDate(item.updated_at)} />
      </div>
    </Card>
  );
}

function Detail({ label, value, mono }: { label: string; value: string; mono?: boolean }): JSX.Element {
  return (
    <div className="label-pair">
      <span className="l">{label}</span>
      <span className={mono ? 'v mono' : 'v'}>{value}</span>
    </div>
  );
}

function DetailSkeleton(): JSX.Element {
  return (
    <>
      <div className="page-head">
        <Skeleton width={240} height={30} />
      </div>
      <div className="stat-grid">
        {['a', 'b', 'c', 'd', 'e'].map((k) => (
          <div className="stat" key={k}>
            <Skeleton height={48} />
          </div>
        ))}
      </div>
      <Card pad>
        <Skeleton height={160} />
      </Card>
    </>
  );
}

/** Where "← Back" returns to — set via Link state by the originating page. */
interface BackNav {
  from?: string;
  fromLabel?: string;
}

export function ItemDetailPage(): JSX.Element {
  const { id = '' } = useParams();
  const { state } = useLocation();
  const back = (state as BackNav | null) ?? null;
  const backTo = back?.from ?? routes.items;
  const backLabel = back?.fromLabel ?? 'Items';
  const itemQuery = useItem(id);
  const movementsQuery = useItemMovements(id);
  const [tab, setTab] = useState<DetailTab>('overview');
  const [editOpen, setEditOpen] = useState(false);

  if (itemQuery.isPending) return <DetailSkeleton />;
  if (itemQuery.isError || !itemQuery.data) {
    return <PageError error={itemQuery.error} onRetry={() => void itemQuery.refetch()} />;
  }

  const item = itemQuery.data;
  const unit = item.unit_of_measure;
  const movements = movementsQuery.data?.items ?? [];
  const summary = summariseMovements(movements);

  return (
    <>
      <PageHeader
        title={item.name}
        sub={
          <span className="flex items-center gap-8">
            <span className="mono">{item.sku}</span>
            <ItemTypeBadge type={item.type} />
            <ItemStatusBadge status={item.status} />
          </span>
        }
        actions={
          <>
            <ButtonLink to={backTo} variant="sec">
              ← {backLabel}
            </ButtonLink>
            <Button variant="pri" onClick={() => setEditOpen(true)}>
              Edit
            </Button>
          </>
        }
      />

      <div className="stat-grid">
        <Stat label="Current stock" value={formatQuantity(item.stock_quantity, unit)} />
        <Stat
          label="Reorder threshold"
          value={item.reorder_threshold ? formatQuantity(item.reorder_threshold, unit) : '—'}
        />
        <Stat
          label="Last movement"
          value={summary.lastMovementAt ? formatRelative(summary.lastMovementAt) : '—'}
        />
        <Stat label="Total inbound" value={formatQuantity(summary.totalInbound, unit)} />
        <Stat label="Total outbound" value={formatQuantity(summary.totalOutbound, unit)} />
      </div>

      <Tabs tabs={[...TABS]} value={tab} onChange={setTab} ariaLabel="Item detail sections" />

      {tab === 'overview' ? (
        <Overview item={item} />
      ) : (
        <ItemMovementsTab movements={movements} unit={unit} loading={movementsQuery.isPending} />
      )}

      {editOpen && <ItemFormDrawer mode="edit" item={item} onClose={() => setEditOpen(false)} />}
    </>
  );
}
