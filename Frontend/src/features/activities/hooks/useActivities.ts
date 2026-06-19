import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query';

import { logger } from '@/lib/logger';
import type { Activity, ActivityCreateRequest, Paginated } from '@/types/api.types';

import { createActivity, listActivities } from '../api/activities.api';
import { activityKeys, type ActivitySubject } from '../activities.keys';

export function useActivities(subject: ActivitySubject): UseQueryResult<Paginated<Activity>> {
  const { customerId, leadId } = subject;
  return useQuery({
    queryKey: activityKeys.list(subject),
    queryFn: () =>
      listActivities({ customer_id: customerId, lead_id: leadId }),
    enabled: Boolean(customerId) || Boolean(leadId),
  });
}

export function useLogActivity(
  subject: ActivitySubject,
): UseMutationResult<Activity, unknown, ActivityCreateRequest> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: ActivityCreateRequest) => createActivity(body),
    onSuccess: (activity) => {
      logger.info('activities.create', { activityId: activity.id, type: activity.type });
      void queryClient.invalidateQueries({ queryKey: activityKeys.list(subject) });
    },
  });
}
