import type { ListBatchesParams } from './api/batches.api';

/** React Query key factory for the batches (lots) domain. */
export const batchKeys = {
  all: ['batches'] as const,
  lists: () => [...batchKeys.all, 'list'] as const,
  list: (params: ListBatchesParams) => [...batchKeys.lists(), params] as const,
};
