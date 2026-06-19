import type { ListLeadsParams } from './api/leads.api';

export const leadKeys = {
  all: ['leads'] as const,
  list: (params: ListLeadsParams) => ['leads', 'list', params] as const,
  detail: (id: string) => ['leads', 'detail', id] as const,
  // Score reads come from the Intelligence service (separate origin).
  scores: ['leads', 'scores'] as const,
  scoreList: (assignedTo?: string) => ['leads', 'scores', 'list', assignedTo ?? null] as const,
  score: (id: string) => ['leads', 'scores', 'detail', id] as const,
};
