import { apiGet, apiPost } from '@/lib/api/client';
import type { Activity, ActivityCreateRequest, Paginated } from '@/types/api.types';

const ACTIVITIES = '/api/v1/activities';

export interface ListActivitiesParams {
  customer_id?: string;
  lead_id?: string;
  limit?: number;
}

function listQuery(params: ListActivitiesParams): Record<string, string | number> {
  const query: Record<string, string | number> = {};
  if (params.customer_id) query.customer_id = params.customer_id;
  if (params.lead_id) query.lead_id = params.lead_id;
  if (params.limit !== undefined) query.limit = params.limit;
  return query;
}

export function listActivities(params: ListActivitiesParams): Promise<Paginated<Activity>> {
  return apiGet<Paginated<Activity>>(ACTIVITIES, { params: listQuery(params) });
}

export function createActivity(body: ActivityCreateRequest): Promise<Activity> {
  return apiPost<Activity, ActivityCreateRequest>(ACTIVITIES, body);
}
