import { useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';

import { routes } from '@/app/routes';
import { PageError } from '@/components/errors/PageError';
import { PageHeader } from '@/components/layout/PageHeader';
import { useToast } from '@/components/toast/useToast';
import { Button, ButtonLink } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Modal } from '@/components/ui/Modal';
import { Skeleton } from '@/components/ui/Skeleton';
import { Tabs } from '@/components/ui/Tabs';
import { useApiError } from '@/hooks/useApiError';
import { formatCurrency, formatDate, formatQuantity, formatRelative } from '@/lib/format';
import type { FinishedItemDetail, Item, RawItemDetail } from '@/types/api.types';

import { ItemStatusBadge, ItemTypeBadge } from '../components/ItemBadges';
import { ItemFormDrawer } from '../components/ItemFormDrawer';
import { ItemMovementsTab } from '../components/ItemMovementsTab';
import { useDeleteItem, useItem, useItemMovements } from '../hooks/useItems';
import { parseIngredients, summariseMovements } from '../item.transform';
import {
  dosageFormLabel,
  drugScheduleLabel,
  materialClassificationLabel,
  pharmacopoeiaLabel,
  storageConditionLabel,
} from '../pharma';
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
        <Detail label="Storage condition" value={storageConditionLabel(item.storage_condition)} />
        <Detail
          label="Shelf life"
          value={item.shelf_life_days != null ? `${item.shelf_life_days} days` : '—'}
        />
        <div className="full">
          <Detail label="Description" value={item.description ?? '—'} />
        </div>
        <Detail label="Created" value={formatDate(item.created_at)} />
        <Detail label="Last updated" value={formatDate(item.updated_at)} />
      </div>

      {item.raw_detail && <RawDetail detail={item.raw_detail} />}
      {item.finished_detail && <FinishedDetail detail={item.finished_detail} />}
    </Card>
  );
}

function RawDetail({ detail }: { detail: RawItemDetail }): JSX.Element {
  return (
    <>
      <div className="divider mt-16" />
      <div className="sect-title mb-8">Raw material details</div>
      <div className="item-overview">
        <Detail
          label="Classification"
          value={materialClassificationLabel(detail.material_classification)}
        />
        <Detail label="Pharmacopoeia" value={pharmacopoeiaLabel(detail.pharmacopoeia)} />
        <Detail label="Hazardous" value={detail.is_hazardous ? 'Yes' : 'No'} />
      </div>
    </>
  );
}

function FinishedDetail({ detail }: { detail: FinishedItemDetail }): JSX.Element {
  return (
    <>
      <div className="divider mt-16" />
      <div className="sect-title mb-8">Finished product details</div>
      <div className="item-overview">
        <Detail label="Generic name" value={detail.generic_name ?? '—'} />
        <Detail label="Brand name" value={detail.brand_name ?? '—'} />
        <Detail label="Strength" value={detail.strength ?? '—'} />
        <Detail label="Dosage form" value={dosageFormLabel(detail.dosage_form)} />
        <Detail label="Pack size" value={detail.pack_size ?? '—'} />
        <Detail label="Container spec" value={detail.container_specification ?? '—'} />
        <Detail
          label="Selling price"
          value={detail.selling_price ? formatCurrency(detail.selling_price) : '—'}
        />
        <Detail label="MRP" value={detail.mrp ? formatCurrency(detail.mrp) : '—'} />
        <Detail label="Drug schedule" value={drugScheduleLabel(detail.drug_schedule)} />
        <Detail label="Prescription" value={detail.is_prescription_required ? 'Required' : 'OTC'} />
        <Detail label="License number" value={detail.license_number ?? '—'} />
        <Detail label="Registration code" value={detail.registration_code ?? '—'} />
        <div className="full">
          <Ingredients raw={detail.ingredients} />
        </div>
      </div>
    </>
  );
}

function Ingredients({ raw }: { raw: string | null }): JSX.Element {
  const lines = parseIngredients(raw);
  if (!lines) {
    return <Detail label="Ingredients" value={raw ?? '—'} />;
  }
  return (
    <div className="label-pair">
      <span className="l">Ingredients</span>
      <span className="v">
        {lines.map((ing) => (
          <div key={ing.name}>
            {ing.name}
            {ing.qty ? (
              <span className="muted">
                {' — '}
                {ing.qty}
                {ing.unit ? ` ${ing.unit}` : ''}
              </span>
            ) : null}
          </div>
        ))}
      </span>
    </div>
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
  const navigate = useNavigate();
  const toast = useToast();
  const reportApiError = useApiError();
  const itemQuery = useItem(id);
  const movementsQuery = useItemMovements(id);
  const deleteMut = useDeleteItem();
  const [tab, setTab] = useState<DetailTab>('overview');
  const [editOpen, setEditOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  if (itemQuery.isPending) return <DetailSkeleton />;
  if (itemQuery.isError || !itemQuery.data) {
    return <PageError error={itemQuery.error} onRetry={() => void itemQuery.refetch()} />;
  }

  const item = itemQuery.data;
  const unit = item.unit_of_measure;
  const movements = movementsQuery.data?.items ?? [];
  const summary = summariseMovements(movements);

  const onConfirmDelete = (): void => {
    deleteMut.mutate(item.id, {
      onSuccess: () => {
        toast.success(`${item.name} deactivated.`);
        navigate(backTo);
      },
      onError: (error) => reportApiError(error, { scope: 'items.delete' }),
    });
  };

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
            {item.is_active && (
              <Button variant="dng" onClick={() => setConfirmDelete(true)}>
                Deactivate
              </Button>
            )}
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

      {confirmDelete && (
        <Modal
          open
          onClose={() => setConfirmDelete(false)}
          title={`Deactivate ${item.name}?`}
          sub="The item is hidden from the catalogue and can't be added to new orders. Its history (movements, lots, orders) is preserved and it can be reactivated later."
          tone="danger"
          footer={
            <>
              <Button variant="sec" onClick={() => setConfirmDelete(false)}>
                Cancel
              </Button>
              <Button variant="dng" onClick={onConfirmDelete} loading={deleteMut.isPending}>
                Deactivate
              </Button>
            </>
          }
        >
          <p className="text-muted">This is a soft delete — nothing is permanently removed.</p>
        </Modal>
      )}
    </>
  );
}
