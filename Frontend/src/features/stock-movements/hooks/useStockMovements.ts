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
import type { ManualAdjustmentRequest, Paginated, StockMovement } from '@/types/api.types';

import { createAdjustment, listStockMovements, type ListMovementsParams } from '../api/sm.api';
import { smKeys } from '../sm.keys';

export function useStockMovements(params: ListMovementsParams): UseQueryResult<Paginated<StockMovement>> {
  return useQuery({
    queryKey: smKeys.list(params),
    queryFn: () => listStockMovements(params),
    placeholderData: keepPreviousData,
  });
}

export function useCreateAdjustment(): UseMutationResult<StockMovement, unknown, ManualAdjustmentRequest> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: ManualAdjustmentRequest) => createAdjustment(body),
    onSuccess: (movement) => {
      logger.info('stock-movements.adjustment', {
        movementId: movement.id,
        itemId: movement.item_id,
        direction: movement.direction,
      });
      // A manual adjustment mutates item stock — refresh ledger + item caches.
      void queryClient.invalidateQueries({ queryKey: smKeys.all });
      void queryClient.invalidateQueries({ queryKey: itemKeys.all });
    },
  });
}
