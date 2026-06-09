import { apiGet, apiPost } from '@/lib/api/client';
import type { ManualAdjustmentRequest, Paginated, StockMovement } from '@/types/api.types';
import type { MovementDirection, MovementReason } from '@/types/enums';

const STOCK_MOVEMENTS = '/api/v1/stock-movements';

export interface ListMovementsParams {
  limit: number;
  offset: number;
  item_id?: string;
  direction?: MovementDirection;
  reason?: MovementReason;
}

function listQuery(params: ListMovementsParams): Record<string, string | number> {
  const query: Record<string, string | number> = { limit: params.limit, offset: params.offset };
  if (params.item_id) query.item_id = params.item_id;
  if (params.direction) query.direction = params.direction;
  if (params.reason) query.reason = params.reason;
  return query;
}

export function listStockMovements(params: ListMovementsParams): Promise<Paginated<StockMovement>> {
  return apiGet<Paginated<StockMovement>>(STOCK_MOVEMENTS, { params: listQuery(params) });
}

/** The only write to the ledger — append-only, no PATCH/DELETE exists. */
export function createAdjustment(body: ManualAdjustmentRequest): Promise<StockMovement> {
  return apiPost<StockMovement, ManualAdjustmentRequest>(`${STOCK_MOVEMENTS}/adjustments`, body);
}
