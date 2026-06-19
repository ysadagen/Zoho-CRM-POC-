import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query';

import { logger } from '@/lib/logger';
import type {
  Lead,
  LeadCreateRequest,
  LeadDetail,
  LeadScoreDetail,
  LeadScoreList,
  LeadUpdateRequest,
  Paginated,
  StageTransitionRequest,
} from '@/types/api.types';

import {
  createLead,
  getLead,
  getLeadScore,
  listLeadScores,
  listLeads,
  transitionLead,
  updateLead,
  type ListLeadScoresParams,
  type ListLeadsParams,
} from '../api/leads.api';
import { leadKeys } from '../leads.keys';

export function useLeadsList(params: ListLeadsParams): UseQueryResult<Paginated<Lead>> {
  return useQuery({
    queryKey: leadKeys.list(params),
    queryFn: () => listLeads(params),
    placeholderData: keepPreviousData,
  });
}

export function useLead(id: string): UseQueryResult<LeadDetail> {
  return useQuery({
    queryKey: leadKeys.detail(id),
    queryFn: () => getLead(id),
    enabled: Boolean(id),
  });
}

/** Latest score per active lead (Intelligence) — joined to the list by id. */
export function useLeadScores(params: ListLeadScoresParams = {}): UseQueryResult<LeadScoreList> {
  return useQuery({
    queryKey: leadKeys.scoreList(params.assigned_to_user_id),
    queryFn: () => listLeadScores(params),
    placeholderData: keepPreviousData,
  });
}

export function useLeadScore(id: string): UseQueryResult<LeadScoreDetail> {
  return useQuery({
    queryKey: leadKeys.score(id),
    queryFn: () => getLeadScore(id),
    enabled: Boolean(id),
  });
}

export function useCreateLead(): UseMutationResult<Lead, unknown, LeadCreateRequest> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: LeadCreateRequest) => createLead(body),
    onSuccess: (lead) => {
      logger.info('leads.create', { leadId: lead.id, leadNumber: lead.lead_number });
      void queryClient.invalidateQueries({ queryKey: leadKeys.all });
    },
  });
}

export function useUpdateLead(id: string): UseMutationResult<Lead, unknown, LeadUpdateRequest> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: LeadUpdateRequest) => updateLead(id, body),
    onSuccess: (lead) => {
      logger.info('leads.update', { leadId: lead.id });
      void queryClient.invalidateQueries({ queryKey: leadKeys.all });
    },
  });
}

export function useTransitionLead(
  id: string,
): UseMutationResult<Lead, unknown, StageTransitionRequest> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: StageTransitionRequest) => transitionLead(id, body),
    onSuccess: (lead) => {
      logger.info('leads.transition', { leadId: lead.id, stage: lead.stage });
      void queryClient.invalidateQueries({ queryKey: leadKeys.all });
    },
  });
}
