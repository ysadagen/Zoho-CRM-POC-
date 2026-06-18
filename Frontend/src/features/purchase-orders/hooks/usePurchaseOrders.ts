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
import type {
  Paginated,
  PurchaseOrder,
  PurchaseOrderCreateRequest,
  PurchaseOrderReceiveRequest,
} from '@/types/api.types';

import {
  createPurchaseOrder,
  getPurchaseOrder,
  listPurchaseOrders,
  receivePurchaseOrder,
  type ListPurchaseOrdersParams,
} from '../api/po.api';
import { poKeys } from '../po.keys';

export function usePurchaseOrdersList(
  params: ListPurchaseOrdersParams,
): UseQueryResult<Paginated<PurchaseOrder>> {
  return useQuery({
    queryKey: poKeys.list(params),
    queryFn: () => listPurchaseOrders(params),
    placeholderData: keepPreviousData,
  });
}

export function usePurchaseOrder(id: string): UseQueryResult<PurchaseOrder> {
  return useQuery({ queryKey: poKeys.detail(id), queryFn: () => getPurchaseOrder(id), enabled: Boolean(id) });
}

export function useCreatePurchaseOrder(): UseMutationResult<
  PurchaseOrder,
  unknown,
  PurchaseOrderCreateRequest
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: PurchaseOrderCreateRequest) => createPurchaseOrder(body),
    onSuccess: (po) => {
      logger.info('purchase-orders.create', { poId: po.id, poNumber: po.po_number });
      void queryClient.invalidateQueries({ queryKey: poKeys.all });
    },
  });
}

export function useReceivePurchaseOrder(
  id: string,
): UseMutationResult<PurchaseOrder, unknown, PurchaseOrderReceiveRequest> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: PurchaseOrderReceiveRequest) => receivePurchaseOrder(id, body),
    onSuccess: (po) => {
      logger.info('purchase-orders.receive', { poId: po.id, poNumber: po.po_number });
      // Receiving mutates item stock — refresh PO + item caches.
      void queryClient.invalidateQueries({ queryKey: poKeys.all });
      void queryClient.invalidateQueries({ queryKey: itemKeys.all });
    },
  });
}
