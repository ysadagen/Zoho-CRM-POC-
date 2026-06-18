import { apiDelete, apiGet, apiPatch, apiPost } from '@/lib/api/client';
import type {
  Item,
  ItemCreateRequest,
  ItemUpdateRequest,
  Paginated,
  StockMovement,
} from '@/types/api.types';
import type { ItemStatus, ItemType } from '@/types/enums';

const ITEMS = '/api/v1/items';
const STOCK_MOVEMENTS = '/api/v1/stock-movements';

export interface ListItemsParams {
  limit: number;
  offset: number;
  type?: ItemType;
  search?: string;
  /** Derived stock-health buckets to match; any-of (sent as repeated `status`). */
  statuses?: ItemStatus[];
  /** Include soft-deleted (inactive) items in the result. Default: false. */
  includeInactive?: boolean;
}

/** POST /items returns a minimal envelope; GET /items/{id} has the full record. */
export interface ItemCreated {
  id: string;
  sku: string;
  name: string;
  created_at: string;
}

function listQuery(params: ListItemsParams): Record<string, string | number | string[]> {
  const query: Record<string, string | number | string[]> = {
    limit: params.limit,
    offset: params.offset,
  };
  if (params.type) query.type = params.type;
  const search = params.search?.trim();
  if (search) query.search = search;
  if (params.statuses && params.statuses.length > 0) query.status = params.statuses;
  if (params.includeInactive) query.include_inactive = 'true';
  return query;
}

export function listItems(params: ListItemsParams): Promise<Paginated<Item>> {
  // `indexes: null` serialises arrays as repeated keys (`status=A&status=B`),
  // which is what FastAPI's `list[ItemStatus]` query param expects.
  return apiGet<Paginated<Item>>(ITEMS, {
    params: listQuery(params),
    paramsSerializer: { indexes: null },
  });
}

export function getItem(id: string): Promise<Item> {
  return apiGet<Item>(`${ITEMS}/${id}`);
}

export function createItem(body: ItemCreateRequest): Promise<ItemCreated> {
  return apiPost<ItemCreated, ItemCreateRequest>(ITEMS, body);
}

export function updateItem(id: string, body: ItemUpdateRequest): Promise<Item> {
  return apiPatch<Item, ItemUpdateRequest>(`${ITEMS}/${id}`, body);
}

/** Soft-delete (deactivate) an item — the row survives for audit (#1). 204. */
export function deleteItem(id: string): Promise<void> {
  return apiDelete<void>(`${ITEMS}/${id}`);
}

/** Audit movements for one item — powers the detail stat cards + history tab. */
export function listItemMovements(itemId: string, limit = 50): Promise<Paginated<StockMovement>> {
  return apiGet<Paginated<StockMovement>>(STOCK_MOVEMENTS, {
    params: { item_id: itemId, limit },
  });
}
