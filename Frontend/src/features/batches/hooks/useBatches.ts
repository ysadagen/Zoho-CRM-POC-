import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query';

import { itemKeys } from '@/features/items/items.keys';
import { logger } from '@/lib/logger';
import type { Batch, BatchCreateRequest, Paginated } from '@/types/api.types';
import type { BatchStatus } from '@/types/enums';

import {
  changeBatchStatus,
  createBatch,
  listBatches,
  type ListBatchesParams,
} from '../api/batches.api';
import { batchKeys } from '../batches.keys';

export function useBatchesList(params: ListBatchesParams): UseQueryResult<Paginated<Batch>> {
  return useQuery({
    queryKey: batchKeys.list(params),
    queryFn: () => listBatches(params),
    placeholderData: keepPreviousData,
  });
}

export function useCreateBatch(): UseMutationResult<Batch, unknown, BatchCreateRequest> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: BatchCreateRequest) => createBatch(body),
    onSuccess: (batch) => {
      logger.info('batches.create', {
        batchId: batch.id,
        itemId: batch.item_id,
        batchNumber: batch.batch_number,
      });
      // Opening-balance lots don't change item stock, but the item's lot
      // coverage changes — refresh both caches.
      void queryClient.invalidateQueries({ queryKey: batchKeys.all });
      void queryClient.invalidateQueries({ queryKey: itemKeys.all });
    },
  });
}

export function useChangeBatchStatus(): UseMutationResult<
  Batch,
  unknown,
  { id: string; status: BatchStatus }
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }) => changeBatchStatus(id, status),
    onSuccess: (batch) => {
      logger.info('batches.status', { batchId: batch.id, status: batch.batch_status });
      // A recall/reject removes the lot from shipping — refresh lots + items.
      void queryClient.invalidateQueries({ queryKey: batchKeys.all });
      void queryClient.invalidateQueries({ queryKey: itemKeys.all });
    },
  });
}
