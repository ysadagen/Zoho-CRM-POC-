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
  Paginated,
  PurchaseOrder,
  Vendor,
  VendorCreateRequest,
  VendorItemTerm,
  VendorItemTermCreateRequest,
  VendorItemTermUpdateRequest,
  VendorUpdateRequest,
} from '@/types/api.types';

import {
  createVendor,
  createVendorTerm,
  deleteVendorTerm,
  getVendor,
  listVendorPurchaseOrders,
  listVendorTerms,
  listVendors,
  updateVendor,
  updateVendorTerm,
  type ListVendorsParams,
  type VendorCreated,
} from '../api/vendors.api';
import { vendorKeys } from '../vendors.keys';

export function useVendorsList(params: ListVendorsParams): UseQueryResult<Paginated<Vendor>> {
  return useQuery({
    queryKey: vendorKeys.list(params),
    queryFn: () => listVendors(params),
    placeholderData: keepPreviousData,
  });
}

export function useVendor(id: string): UseQueryResult<Vendor> {
  return useQuery({ queryKey: vendorKeys.detail(id), queryFn: () => getVendor(id), enabled: Boolean(id) });
}

export function useVendorPurchaseOrders(id: string): UseQueryResult<Paginated<PurchaseOrder>> {
  return useQuery({
    queryKey: vendorKeys.purchaseOrders(id),
    queryFn: () => listVendorPurchaseOrders(id),
    enabled: Boolean(id),
  });
}

export function useVendorTerms(id: string): UseQueryResult<Paginated<VendorItemTerm>> {
  return useQuery({
    queryKey: vendorKeys.terms(id),
    queryFn: () => listVendorTerms(id),
    enabled: Boolean(id),
  });
}

export function useCreateVendor(): UseMutationResult<VendorCreated, unknown, VendorCreateRequest> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: VendorCreateRequest) => createVendor(body),
    onSuccess: (created) => {
      logger.info('vendors.create', { vendorId: created.id, vendor: created.vendor_name });
      void queryClient.invalidateQueries({ queryKey: vendorKeys.all });
    },
  });
}

export function useUpdateVendor(id: string): UseMutationResult<Vendor, unknown, VendorUpdateRequest> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: VendorUpdateRequest) => updateVendor(id, body),
    onSuccess: (vendor) => {
      logger.info('vendors.update', { vendorId: vendor.id, vendor: vendor.vendor_name });
      void queryClient.invalidateQueries({ queryKey: vendorKeys.all });
    },
  });
}

export function useCreateTerm(
  vendorId: string,
): UseMutationResult<VendorItemTerm, unknown, VendorItemTermCreateRequest> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: VendorItemTermCreateRequest) => createVendorTerm(vendorId, body),
    onSuccess: (term) => {
      logger.info('vendors.term.create', { vendorId, termId: term.id, itemId: term.item_id });
      void queryClient.invalidateQueries({ queryKey: vendorKeys.terms(vendorId) });
    },
  });
}

export function useUpdateTerm(
  vendorId: string,
): UseMutationResult<VendorItemTerm, unknown, { termId: string; body: VendorItemTermUpdateRequest }> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ termId, body }: { termId: string; body: VendorItemTermUpdateRequest }) =>
      updateVendorTerm(vendorId, termId, body),
    onSuccess: (term) => {
      logger.info('vendors.term.update', { vendorId, termId: term.id });
      void queryClient.invalidateQueries({ queryKey: vendorKeys.terms(vendorId) });
    },
  });
}

export function useDeleteTerm(vendorId: string): UseMutationResult<void, unknown, string> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (termId: string) => deleteVendorTerm(vendorId, termId),
    onSuccess: (_data, termId) => {
      logger.info('vendors.term.delete', { vendorId, termId });
      void queryClient.invalidateQueries({ queryKey: vendorKeys.terms(vendorId) });
    },
  });
}
