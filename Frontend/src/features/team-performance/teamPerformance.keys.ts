import type { ListEffortEfficiencyParams } from './api/teamPerformance.api';

export const teamPerformanceKeys = {
  all: ['team-performance'] as const,
  effortEfficiency: (params: ListEffortEfficiencyParams) =>
    ['team-performance', 'effort-efficiency', params] as const,
};
