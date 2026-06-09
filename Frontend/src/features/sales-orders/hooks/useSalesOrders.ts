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
import type { Paginated, SalesOrder, SalesOrderCreateRequest } from '@/types/api.types';

import {
  createSalesOrder,
  getSalesOrder,
  listSalesOrders,
  shipSalesOrder,
  type ListSalesOrdersParams,
} from '../api/so.api';
import { soKeys } from '../so.keys';

export function useSalesOrdersList(
  params: ListSalesOrdersParams,
): UseQueryResult<Paginated<SalesOrder>> {
  return useQuery({
    queryKey: soKeys.list(params),
    queryFn: () => listSalesOrders(params),
    placeholderData: keepPreviousData,
  });
}

export function useSalesOrder(id: string): UseQueryResult<SalesOrder> {
  return useQuery({ queryKey: soKeys.detail(id), queryFn: () => getSalesOrder(id), enabled: Boolean(id) });
}

export function useCreateSalesOrder(): UseMutationResult<SalesOrder, unknown, SalesOrderCreateRequest> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: SalesOrderCreateRequest) => createSalesOrder(body),
    onSuccess: (so) => {
      logger.info('sales-orders.create', { soId: so.id, soNumber: so.so_number });
      void queryClient.invalidateQueries({ queryKey: soKeys.all });
    },
  });
}

export function useShipSalesOrder(id: string): UseMutationResult<SalesOrder, unknown, void> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => shipSalesOrder(id),
    onSuccess: (so) => {
      logger.info('sales-orders.ship', { soId: so.id, soNumber: so.so_number });
      // Shipping mutates item stock — refresh SO + item caches.
      void queryClient.invalidateQueries({ queryKey: soKeys.all });
      void queryClient.invalidateQueries({ queryKey: itemKeys.all });
    },
  });
}
