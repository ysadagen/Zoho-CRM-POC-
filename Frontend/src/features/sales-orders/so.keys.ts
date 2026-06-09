import type { ListSalesOrdersParams } from './api/so.api';

export const soKeys = {
  all: ['sales-orders'] as const,
  list: (params: ListSalesOrdersParams) => ['sales-orders', 'list', params] as const,
  detail: (id: string) => ['sales-orders', 'detail', id] as const,
};
