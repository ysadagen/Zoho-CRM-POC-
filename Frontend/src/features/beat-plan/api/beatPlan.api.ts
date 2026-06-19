import { apiGet } from '@/lib/api/client';
import { env } from '@/config/env';
import type { BeatPlan, Paginated, User } from '@/types/api.types';

const BEAT_PLAN = '/api/v1/intelligence/beat-plan';
const USERS = '/api/v1/users';

export interface GetBeatPlanParams {
  rep_user_id: string;
  max_visits?: number;
}

function planQuery(params: GetBeatPlanParams): Record<string, string | number> {
  const query: Record<string, string | number> = { rep_user_id: params.rep_user_id };
  if (params.max_visits !== undefined) query.max_visits = params.max_visits;
  return query;
}

/** The beat plan lives on the Intelligence service — reached via a per-request baseURL override. */
export function getBeatPlan(params: GetBeatPlanParams): Promise<BeatPlan> {
  return apiGet<BeatPlan>(BEAT_PLAN, {
    baseURL: env.intelligenceBaseUrl,
    params: planQuery(params),
  });
}

/** Reps come from the Backend (default base) — the rep picker for the plan. */
export function listReps(): Promise<Paginated<User>> {
  return apiGet<Paginated<User>>(USERS, { params: { limit: 100 } });
}
