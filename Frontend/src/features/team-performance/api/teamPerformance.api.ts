import { apiGet } from '@/lib/api/client';
import { env } from '@/config/env';
import type { EffortEfficiencyList } from '@/types/api.types';

const EFFORT_EFFICIENCY = '/api/v1/intelligence/effort-efficiency';

export interface ListEffortEfficiencyParams {
  period_start?: string;
  period_end?: string;
}

function listQuery(params: ListEffortEfficiencyParams): Record<string, string> {
  const query: Record<string, string> = {};
  if (params.period_start) query.period_start = params.period_start;
  if (params.period_end) query.period_end = params.period_end;
  return query;
}

/**
 * Live per-rep effort × efficiency cohort. Served by the Intelligence
 * service (separate origin) via the shared client's per-request `baseURL`.
 */
export function listEffortEfficiency(
  params: ListEffortEfficiencyParams = {},
): Promise<EffortEfficiencyList> {
  return apiGet<EffortEfficiencyList>(EFFORT_EFFICIENCY, {
    baseURL: env.intelligenceBaseUrl,
    params: listQuery(params),
  });
}
