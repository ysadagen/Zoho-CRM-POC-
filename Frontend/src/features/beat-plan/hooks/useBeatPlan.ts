import { useQuery, type UseQueryResult } from '@tanstack/react-query';

import type { BeatPlan, Paginated, User } from '@/types/api.types';

import { getBeatPlan, listReps } from '../api/beatPlan.api';
import { beatPlanKeys } from '../beatPlan.keys';

export function useReps(): UseQueryResult<Paginated<User>> {
  return useQuery({
    queryKey: beatPlanKeys.reps(),
    queryFn: () => listReps(),
  });
}

export function useBeatPlan(
  repUserId: string,
  maxVisits?: number,
): UseQueryResult<BeatPlan> {
  return useQuery({
    queryKey: beatPlanKeys.plan(repUserId, maxVisits),
    queryFn: () => getBeatPlan({ rep_user_id: repUserId, max_visits: maxVisits }),
    enabled: Boolean(repUserId),
  });
}
