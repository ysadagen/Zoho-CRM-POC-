import { keepPreviousData, useQuery, type UseQueryResult } from '@tanstack/react-query';

import type { EffortEfficiencyList } from '@/types/api.types';

import {
  listEffortEfficiency,
  type ListEffortEfficiencyParams,
} from '../api/teamPerformance.api';
import { teamPerformanceKeys } from '../teamPerformance.keys';

export function useEffortEfficiency(
  params: ListEffortEfficiencyParams = {},
): UseQueryResult<EffortEfficiencyList> {
  return useQuery({
    queryKey: teamPerformanceKeys.effortEfficiency(params),
    queryFn: () => listEffortEfficiency(params),
    placeholderData: keepPreviousData,
  });
}
