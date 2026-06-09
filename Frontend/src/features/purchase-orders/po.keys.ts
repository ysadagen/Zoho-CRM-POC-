import type { ListPurchaseOrdersParams } from './api/po.api';

export const poKeys = {
  all: ['purchase-orders'] as const,
  list: (params: ListPurchaseOrdersParams) => ['purchase-orders', 'list', params] as const,
  detail: (id: string) => ['purchase-orders', 'detail', id] as const,
};
