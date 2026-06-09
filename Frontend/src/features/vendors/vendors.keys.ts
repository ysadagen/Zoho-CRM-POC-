import type { ListVendorsParams } from './api/vendors.api';

export const vendorKeys = {
  all: ['vendors'] as const,
  list: (params: ListVendorsParams) => ['vendors', 'list', params] as const,
  detail: (id: string) => ['vendors', 'detail', id] as const,
  purchaseOrders: (id: string) => ['vendors', 'purchase-orders', id] as const,
  terms: (id: string) => ['vendors', 'terms', id] as const,
};
