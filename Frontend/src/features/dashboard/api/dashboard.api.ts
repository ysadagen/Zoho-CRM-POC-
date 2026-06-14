/**
 * Dashboard data access — thin typed wrappers over the Backend list endpoints.
 *
 * The dashboard has no dedicated aggregate endpoint, so it derives its figures
 * from the standard resource lists:
 *  - the item catalog powers Total Stock Value, Low Stock count + Needs Attention
 *    and the item-name lookup for Recent Movements;
 *  - draft PO/SO counts come "for free" from the pagination `total` of a
 *    `limit=1` query, so we never fetch rows we don't render.
 */
import { apiGet } from '@/lib/api/client';
import type { Item, Paginated, PurchaseOrder, SalesOrder, StockMovement } from '@/types/api.types';

const ITEMS = '/api/v1/items';
const STOCK_MOVEMENTS = '/api/v1/stock-movements';
const PURCHASE_ORDERS = '/api/v1/purchase-orders';
const SALES_ORDERS = '/api/v1/sales-orders';

/** Upper bound on the catalog pulled for dashboard aggregates (Backend caps at 100). */
export const DASHBOARD_ITEM_LIMIT = 100;
/** How many movements the "Recent Stock Movements" card shows. */
export const RECENT_MOVEMENT_LIMIT = 5;

export async function fetchDashboardItems(): Promise<Item[]> {
  const res = await apiGet<Paginated<Item>>(ITEMS, { params: { limit: DASHBOARD_ITEM_LIMIT } });
  return res.items;
}

export async function fetchRecentMovements(): Promise<StockMovement[]> {
  const res = await apiGet<Paginated<StockMovement>>(STOCK_MOVEMENTS, {
    params: { limit: RECENT_MOVEMENT_LIMIT },
  });
  return res.items;
}

export async function fetchDraftPurchaseOrderCount(): Promise<number> {
  const res = await apiGet<Paginated<PurchaseOrder>>(PURCHASE_ORDERS, {
    params: { status: 'DRAFT', limit: 1 },
  });
  return res.total;
}

export async function fetchDraftSalesOrderCount(): Promise<number> {
  const res = await apiGet<Paginated<SalesOrder>>(SALES_ORDERS, {
    params: { status: 'DRAFT', limit: 1 },
  });
  return res.total;
}
