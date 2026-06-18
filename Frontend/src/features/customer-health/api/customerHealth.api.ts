import { apiGet } from '@/lib/api/client';
import { env } from '@/config/env';
import type { CustomerHealthDetail, CustomerHealthList } from '@/types/api.types';
import type { HealthClassification } from '@/types/enums';

const CUSTOMER_HEALTH = '/api/v1/intelligence/customer-health';

export interface ListCustomerHealthParams {
  classification?: HealthClassification;
}

function listQuery(params: ListCustomerHealthParams): Record<string, string> {
  const query: Record<string, string> = {};
  if (params.classification) query.classification = params.classification;
  return query;
}

/** Scores live on the Intelligence service — reached via a per-request baseURL override. */
export function listCustomerHealth(
  params: ListCustomerHealthParams = {},
): Promise<CustomerHealthList> {
  return apiGet<CustomerHealthList>(CUSTOMER_HEALTH, {
    baseURL: env.intelligenceBaseUrl,
    params: listQuery(params),
  });
}

export function getCustomerHealth(customerId: string): Promise<CustomerHealthDetail> {
  return apiGet<CustomerHealthDetail>(`${CUSTOMER_HEALTH}/${customerId}`, {
    baseURL: env.intelligenceBaseUrl,
  });
}
