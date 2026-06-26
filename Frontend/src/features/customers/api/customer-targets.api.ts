import { apiGet, apiPost } from '@/lib/api/client';
import type {
  CustomerTarget,
  CustomerTargetCreateRequest,
} from '@/types/api.types';

const BASE = '/api/v1/customers';

export function listCustomerTargets(customerId: string): Promise<CustomerTarget[]> {
  return apiGet<CustomerTarget[]>(`${BASE}/${customerId}/targets`);
}

export function createCustomerTarget(
  customerId: string,
  body: CustomerTargetCreateRequest,
): Promise<CustomerTarget> {
  return apiPost<CustomerTarget, CustomerTargetCreateRequest>(`${BASE}/${customerId}/targets`, body);
}
