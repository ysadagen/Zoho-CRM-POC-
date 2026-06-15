/**
 * Pure derivations turning Backend payloads into dashboard view-models.
 *
 * No React, no network, no `Date.now()` — everything here is a deterministic
 * function of its inputs so it can be unit-tested exhaustively. The hooks in
 * `hooks/useDashboard.ts` feed live query data through these.
 */
import type { BadgeVariant } from '@/components/ui/Badge';
import type { IconName } from '@/components/ui/Icon';
import type { KpiTone } from '@/components/ui/KpiCard';
import { formatCurrency, formatQuantity, formatSignedQuantity, formatTime } from '@/lib/format';
import type { Item, StockMovement } from '@/types/api.types';
import { ItemStatus, ItemType, MovementReason, MovementReferenceType } from '@/types/enums';

export interface DashboardKpi {
  tone: KpiTone;
  icon: IconName;
  label: string;
  value: string;
  /** Optional secondary line (used only for the honest CRM placeholder). */
  delta?: string;
}

export interface LowStockVM {
  id: string;
  name: string;
  meta: string;
  value: string;
  pct: number;
  critical: boolean;
}

export interface MovementVM {
  id: string;
  itemId: string;
  time: string;
  item: string;
  badgeVariant: BadgeVariant;
  movement: string;
  qty: string;
  reference: string;
}

/**
 * Σ(stock × unit_price) over the fetched catalog. This is a read-only display
 * aggregate the Frontend never writes back, so plain `Number` arithmetic is
 * acceptable here (precision-sensitive monetary writes are computed by the
 * Backend — see Backend_Reference §10.4).
 */
export function totalStockValue(items: Item[]): number {
  return items.reduce((sum, it) => sum + Number(it.stock_quantity) * Number(it.unit_price), 0);
}

export function isLowStock(item: Item): boolean {
  return item.status === ItemStatus.LOW_STOCK || item.status === ItemStatus.NO_STOCK;
}

export function lowStockItems(items: Item[]): Item[] {
  return items.filter(isLowStock);
}

export function toLowStockVM(item: Item): LowStockVM {
  const stock = Number(item.stock_quantity);
  const threshold = item.reorder_threshold == null ? null : Number(item.reorder_threshold);
  const pct =
    threshold && threshold > 0
      ? Math.max(0, Math.min(100, (stock / threshold) * 100))
      : stock > 0
        ? 100
        : 0;
  const typeLabel = item.type === ItemType.RAW ? 'Raw Material' : 'Finished Product';
  const value =
    threshold != null
      ? `${formatQuantity(stock)} / ${formatQuantity(threshold, item.unit_of_measure)}`
      : formatQuantity(stock, item.unit_of_measure);
  return {
    id: item.id,
    name: item.name,
    meta: `${item.sku} · ${typeLabel}`,
    value,
    pct,
    critical: item.status === ItemStatus.NO_STOCK || pct < 50,
  };
}

export function movementBadge(m: StockMovement): { variant: BadgeVariant; label: string } {
  if (m.reason === MovementReason.PURCHASE) return { variant: 'success', label: 'Purchase In' };
  if (m.reason === MovementReason.SALE) return { variant: 'danger', label: 'Sale Out' };
  return { variant: 'warn', label: 'Adjustment' };
}

export function movementReference(m: StockMovement): string {
  if (m.reference_type === MovementReferenceType.PURCHASE_ORDER) return 'Purchase order';
  if (m.reference_type === MovementReferenceType.SALES_ORDER) return 'Sales order';
  return m.remarks ?? 'Manual adjustment';
}

export function toMovementVM(m: StockMovement, items: Map<string, Item>): MovementVM {
  const item = items.get(m.item_id);
  const { variant, label } = movementBadge(m);
  return {
    id: m.id,
    itemId: m.item_id,
    time: formatTime(m.created_at),
    item: item ? item.name : 'Unknown item',
    badgeVariant: variant,
    movement: label,
    qty: formatSignedQuantity(m.signed_quantity, item?.unit_of_measure),
    reference: movementReference(m),
  };
}

export interface KpiInputs {
  items: Item[];
  draftPoCount: number;
  draftSoCount: number;
}

export function buildKpis({ items, draftPoCount, draftSoCount }: KpiInputs): DashboardKpi[] {
  return [
    {
      tone: 'accent',
      icon: 'package',
      label: 'Total Stock Value',
      value: formatCurrency(totalStockValue(items)),
    },
    {
      tone: 'danger',
      icon: 'alertTriangle',
      label: 'Low Stock Items',
      value: String(lowStockItems(items).length),
    },
    {
      tone: 'default',
      icon: 'cart',
      label: 'Open Purchase Orders',
      value: String(draftPoCount),
    },
    {
      tone: 'default',
      icon: 'bag',
      label: 'Open Sales Orders',
      value: String(draftSoCount),
    },
    {
      // No backend yet — the Integration Layer is a later phase. Shown as an
      // honest placeholder rather than a fabricated percentage.
      tone: 'default',
      icon: 'sync',
      label: 'CRM Sync Health',
      value: '—',
      delta: 'Awaiting Integration Layer',
    },
  ];
}

export function greeting(hour: number): string {
  if (hour >= 5 && hour < 12) return 'Good morning';
  if (hour >= 12 && hour < 17) return 'Good afternoon';
  return 'Good evening';
}

export function firstName(fullName: string): string {
  return fullName.trim().split(/\s+/)[0] ?? '';
}
