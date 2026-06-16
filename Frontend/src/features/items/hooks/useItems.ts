import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query';

import { logger } from '@/lib/logger';
import type {
  Item,
  ItemCreateRequest,
  ItemUpdateRequest,
  Paginated,
  StockMovement,
} from '@/types/api.types';

import {
  createItem,
  deleteItem,
  getItem,
  listItemMovements,
  listItems,
  updateItem,
  type ItemCreated,
  type ListItemsParams,
} from '../api/items.api';
import { itemKeys } from '../items.keys';

export function useItemsList(
  params: ListItemsParams,
  options?: { enabled?: boolean },
): UseQueryResult<Paginated<Item>> {
  return useQuery({
    queryKey: itemKeys.list(params),
    queryFn: () => listItems(params),
    // Keep the previous page visible while the next loads (no flash of empty).
    placeholderData: keepPreviousData,
    enabled: options?.enabled ?? true,
  });
}

export function useItem(id: string): UseQueryResult<Item> {
  return useQuery({ queryKey: itemKeys.detail(id), queryFn: () => getItem(id), enabled: Boolean(id) });
}

export function useItemMovements(id: string): UseQueryResult<Paginated<StockMovement>> {
  return useQuery({
    queryKey: itemKeys.movements(id),
    queryFn: () => listItemMovements(id),
    enabled: Boolean(id),
  });
}

export function useCreateItem(): UseMutationResult<ItemCreated, unknown, ItemCreateRequest> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: ItemCreateRequest) => createItem(body),
    onSuccess: (created) => {
      logger.info('items.create', { itemId: created.id, sku: created.sku });
      void queryClient.invalidateQueries({ queryKey: itemKeys.all });
    },
  });
}

export function useUpdateItem(id: string): UseMutationResult<Item, unknown, ItemUpdateRequest> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: ItemUpdateRequest) => updateItem(id, body),
    onSuccess: (item) => {
      logger.info('items.update', { itemId: item.id, sku: item.sku });
      void queryClient.invalidateQueries({ queryKey: itemKeys.all });
    },
  });
}

export function useDeleteItem(): UseMutationResult<void, unknown, string> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteItem(id),
    onSuccess: (_data, id) => {
      logger.info('items.delete', { itemId: id });
      void queryClient.invalidateQueries({ queryKey: itemKeys.all });
    },
  });
}
