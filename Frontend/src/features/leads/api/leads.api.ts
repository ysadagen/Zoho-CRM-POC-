import { env } from '@/config/env';
import { apiGet, apiPatch, apiPost } from '@/lib/api/client';
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
import type { LeadClassification, LeadSource, LeadStage } from '@/types/enums';

const LEADS = '/api/v1/leads';
const LEAD_SCORES = '/api/v1/intelligence/lead-scores';

/** Per-request override so the single axios client hits the Intelligence
 *  service (8002) while keeping the request-id / 401 / error contracts. */
const intel = { baseURL: env.intelligenceBaseUrl };

export interface ListLeadsParams {
  limit: number;
  offset: number;
  search?: string;
  stage?: LeadStage;
  source?: LeadSource;
  assigned_to_user_id?: string;
}

function listQuery(params: ListLeadsParams): Record<string, string | number> {
  const query: Record<string, string | number> = { limit: params.limit, offset: params.offset };
  if (params.search) query.search = params.search;
  if (params.stage) query.stage = params.stage;
  if (params.source) query.source = params.source;
  if (params.assigned_to_user_id) query.assigned_to_user_id = params.assigned_to_user_id;
  return query;
}

// --- Backend (CRM): leads CRUD + stage transition --------------------------

export function listLeads(params: ListLeadsParams): Promise<Paginated<Lead>> {
  return apiGet<Paginated<Lead>>(LEADS, { params: listQuery(params) });
}

export function getLead(id: string): Promise<LeadDetail> {
  return apiGet<LeadDetail>(`${LEADS}/${id}`);
}

export function createLead(body: LeadCreateRequest): Promise<Lead> {
  return apiPost<Lead, LeadCreateRequest>(LEADS, body);
}

export function updateLead(id: string, body: LeadUpdateRequest): Promise<Lead> {
  return apiPatch<Lead, LeadUpdateRequest>(`${LEADS}/${id}`, body);
}

export function transitionLead(id: string, body: StageTransitionRequest): Promise<Lead> {
  return apiPost<Lead, StageTransitionRequest>(`${LEADS}/${id}/transition`, body);
}

// --- Intelligence service: live lead scores --------------------------------

export interface ListLeadScoresParams {
  limit?: number;
  classification?: LeadClassification;
  assigned_to_user_id?: string;
}

export function listLeadScores(params: ListLeadScoresParams = {}): Promise<LeadScoreList> {
  const query: Record<string, string | number> = { limit: params.limit ?? 100 };
  if (params.classification) query.classification = params.classification;
  if (params.assigned_to_user_id) query.assigned_to_user_id = params.assigned_to_user_id;
  return apiGet<LeadScoreList>(LEAD_SCORES, { ...intel, params: query });
}

export function getLeadScore(leadId: string): Promise<LeadScoreDetail> {
  return apiGet<LeadScoreDetail>(`${LEAD_SCORES}/${leadId}`, intel);
}
