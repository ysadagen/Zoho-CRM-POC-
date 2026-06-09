import type { ListMovementsParams } from './api/sm.api';

export const smKeys = {
  all: ['stock-movements'] as const,
  list: (params: ListMovementsParams) => ['stock-movements', 'list', params] as const,
};
