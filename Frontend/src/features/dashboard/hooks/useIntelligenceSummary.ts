import { useQuery, type UseQueryResult } from '@tanstack/react-query';

import { listCustomerHealth } from '@/features/customer-health/api/customerHealth.api';
import { listLeadScores, listLeads } from '@/features/leads/api/leads.api';
import type { CustomerHealthList, LeadScoreList, Paginated, Lead } from '@/types/api.types';
import { LeadClassification } from '@/types/enums';

/** Hot-lead count — from the Intelligence service. */
export function useHotLeadCount(): UseQueryResult<LeadScoreList> {
  return useQuery({
    queryKey: ['dashboard', 'intelligence', 'hot-leads'],
    queryFn: () => listLeadScores({ classification: LeadClassification.HOT, limit: 1 }),
  });
}

/** Full health list — the widget counts AT_RISK + CRITICAL client-side. */
export function useCustomerHealthSummary(): UseQueryResult<CustomerHealthList> {
  return useQuery({
    queryKey: ['dashboard', 'intelligence', 'health'],
    queryFn: () => listCustomerHealth(),
  });
}

/** A wide page of leads for the funnel (counted by stage client-side). */
export function useLeadFunnelSource(): UseQueryResult<Paginated<Lead>> {
  return useQuery({
    queryKey: ['dashboard', 'intelligence', 'funnel'],
    queryFn: () => listLeads({ limit: 200, offset: 0 }),
  });
}
