import type { ListItemsParams } from './api/items.api';

/** React Query key factory for the items domain. */
export const itemKeys = {
  all: ['items'] as const,
  list: (params: ListItemsParams) => ['items', 'list', params] as const,
  detail: (id: string) => ['items', 'detail', id] as const,
  movements: (id: string) => ['items', 'movements', id] as const,
};
