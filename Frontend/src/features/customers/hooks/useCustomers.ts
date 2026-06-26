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
  Customer,
  CustomerCreateRequest,
  CustomerTarget,
  CustomerTargetCreateRequest,
  CustomerUpdateRequest,
  Paginated,
  SalesOrder,
} from '@/types/api.types';

import {
  createCustomer,
  getCustomer,
  listCustomerSalesOrders,
  listCustomers,
  updateCustomer,
  type CustomerCreated,
  type ListCustomersParams,
} from '../api/customers.api';
import { createCustomerTarget, listCustomerTargets } from '../api/customer-targets.api';
import { customerKeys } from '../customers.keys';

export function useCustomersList(params: ListCustomersParams): UseQueryResult<Paginated<Customer>> {
  return useQuery({
    queryKey: customerKeys.list(params),
    queryFn: () => listCustomers(params),
    placeholderData: keepPreviousData,
  });
}

export function useCustomer(id: string): UseQueryResult<Customer> {
  return useQuery({
    queryKey: customerKeys.detail(id),
    queryFn: () => getCustomer(id),
    enabled: Boolean(id),
  });
}

export function useCustomerSalesOrders(id: string): UseQueryResult<Paginated<SalesOrder>> {
  return useQuery({
    queryKey: customerKeys.salesOrders(id),
    queryFn: () => listCustomerSalesOrders(id),
    enabled: Boolean(id),
  });
}

export function useCreateCustomer(): UseMutationResult<CustomerCreated, unknown, CustomerCreateRequest> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: CustomerCreateRequest) => createCustomer(body),
    onSuccess: (created) => {
      logger.info('customers.create', { customerId: created.id, company: created.company_name });
      void queryClient.invalidateQueries({ queryKey: customerKeys.all });
    },
  });
}

export function useUpdateCustomer(id: string): UseMutationResult<Customer, unknown, CustomerUpdateRequest> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: CustomerUpdateRequest) => updateCustomer(id, body),
    onSuccess: (customer) => {
      logger.info('customers.update', { customerId: customer.id, company: customer.company_name });
      void queryClient.invalidateQueries({ queryKey: customerKeys.all });
    },
  });
}

export function useCustomerTargets(customerId: string): UseQueryResult<CustomerTarget[]> {
  return useQuery({
    queryKey: customerKeys.targets(customerId),
    queryFn: () => listCustomerTargets(customerId),
    enabled: Boolean(customerId),
  });
}

export function useCreateCustomerTarget(
  customerId: string,
): UseMutationResult<CustomerTarget, unknown, CustomerTargetCreateRequest> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: CustomerTargetCreateRequest) => createCustomerTarget(customerId, body),
    onSuccess: () => {
      logger.info('customer_targets.create', { customerId });
      void queryClient.invalidateQueries({ queryKey: customerKeys.targets(customerId) });
    },
  });
}
