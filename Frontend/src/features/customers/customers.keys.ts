import type { ListCustomersParams } from './api/customers.api';

export const customerKeys = {
  all: ['customers'] as const,
  list: (params: ListCustomersParams) => ['customers', 'list', params] as const,
  detail: (id: string) => ['customers', 'detail', id] as const,
  salesOrders: (id: string) => ['customers', 'sales-orders', id] as const,
};
