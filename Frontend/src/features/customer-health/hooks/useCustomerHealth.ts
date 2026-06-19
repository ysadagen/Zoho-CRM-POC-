import {
  keepPreviousData,
  useQuery,
  type UseQueryResult,
} from '@tanstack/react-query';

import type { CustomerHealthDetail, CustomerHealthList } from '@/types/api.types';

import {
  getCustomerHealth,
  listCustomerHealth,
  type ListCustomerHealthParams,
} from '../api/customerHealth.api';
import { customerHealthKeys } from '../customerHealth.keys';

export function useCustomerHealthList(
  params: ListCustomerHealthParams,
): UseQueryResult<CustomerHealthList> {
  return useQuery({
    queryKey: customerHealthKeys.list(params),
    queryFn: () => listCustomerHealth(params),
    placeholderData: keepPreviousData,
  });
}

export function useCustomerHealth(id: string): UseQueryResult<CustomerHealthDetail> {
  return useQuery({
    queryKey: customerHealthKeys.detail(id),
    queryFn: () => getCustomerHealth(id),
    enabled: Boolean(id),
  });
}
