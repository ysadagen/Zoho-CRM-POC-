import type { ListCustomerHealthParams } from './api/customerHealth.api';

export const customerHealthKeys = {
  all: ['customer-health'] as const,
  list: (params: ListCustomerHealthParams) => ['customer-health', 'list', params] as const,
  detail: (id: string) => ['customer-health', 'detail', id] as const,
};
