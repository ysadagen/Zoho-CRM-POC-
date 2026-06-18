export const beatPlanKeys = {
  all: ['beat-plan'] as const,
  reps: () => ['beat-plan', 'reps'] as const,
  plan: (repUserId: string, maxVisits: number | undefined) =>
    ['beat-plan', 'plan', repUserId, maxVisits] as const,
};
