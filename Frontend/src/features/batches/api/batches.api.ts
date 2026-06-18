import { apiGet, apiPost } from '@/lib/api/client';
import type { Batch, BatchCreateRequest, Paginated } from '@/types/api.types';
import type { BatchStatus } from '@/types/enums';

export interface BatchStatusChangeRequest {
  status: BatchStatus;
}

const BATCHES = '/api/v1/batches';

export interface ListBatchesParams {
  limit: number;
  offset: number;
  item_id?: string;
  status?: BatchStatus;
  expiring_before?: string;
}

function listQuery(params: ListBatchesParams): Record<string, string | number> {
  const query: Record<string, string | number> = { limit: params.limit, offset: params.offset };
  if (params.item_id) query.item_id = params.item_id;
  if (params.status) query.status = params.status;
  if (params.expiring_before) query.expiring_before = params.expiring_before;
  return query;
}

export function listBatches(params: ListBatchesParams): Promise<Paginated<Batch>> {
  return apiGet<Paginated<Batch>>(BATCHES, { params: listQuery(params) });
}

/** Record an opening-balance lot for existing item stock (Backend §9.7b). */
export function createBatch(body: BatchCreateRequest): Promise<Batch> {
  return apiPost<Batch, BatchCreateRequest>(BATCHES, body);
}

/** Transition a lot's QC status — release / reject / recall (#7). */
export function changeBatchStatus(id: string, status: BatchStatus): Promise<Batch> {
  return apiPost<Batch, BatchStatusChangeRequest>(`${BATCHES}/${id}/status`, { status });
}
