import { apiDelete, apiGet, apiPatch, apiPost } from '@/lib/api/client';
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

const VENDORS = '/api/v1/vendors';
const PURCHASE_ORDERS = '/api/v1/purchase-orders';

export interface ListVendorsParams {
  limit: number;
  offset: number;
  search?: string;
}

export interface VendorCreated {
  id: string;
  vendor_name: string;
}

function listQuery(params: ListVendorsParams): Record<string, string | number> {
  const query: Record<string, string | number> = { limit: params.limit, offset: params.offset };
  const search = params.search?.trim();
  if (search) query.search = search;
  return query;
}

export function listVendors(params: ListVendorsParams): Promise<Paginated<Vendor>> {
  return apiGet<Paginated<Vendor>>(VENDORS, { params: listQuery(params) });
}

export function getVendor(id: string): Promise<Vendor> {
  return apiGet<Vendor>(`${VENDORS}/${id}`);
}

export function createVendor(body: VendorCreateRequest): Promise<VendorCreated> {
  return apiPost<VendorCreated, VendorCreateRequest>(VENDORS, body);
}

export function updateVendor(id: string, body: VendorUpdateRequest): Promise<Vendor> {
  return apiPatch<Vendor, VendorUpdateRequest>(`${VENDORS}/${id}`, body);
}

export function listVendorPurchaseOrders(vendorId: string, limit = 50): Promise<Paginated<PurchaseOrder>> {
  return apiGet<Paginated<PurchaseOrder>>(PURCHASE_ORDERS, {
    params: { vendor_id: vendorId, limit },
  });
}

/* ---- Vendor-item terms (nested under a vendor) ---- */

export function listVendorTerms(vendorId: string, limit = 100): Promise<Paginated<VendorItemTerm>> {
  return apiGet<Paginated<VendorItemTerm>>(`${VENDORS}/${vendorId}/terms`, {
    params: { active_only: true, limit },
  });
}

export function createVendorTerm(
  vendorId: string,
  body: VendorItemTermCreateRequest,
): Promise<VendorItemTerm> {
  return apiPost<VendorItemTerm, VendorItemTermCreateRequest>(`${VENDORS}/${vendorId}/terms`, body);
}

export function updateVendorTerm(
  vendorId: string,
  termId: string,
  body: VendorItemTermUpdateRequest,
): Promise<VendorItemTerm> {
  return apiPatch<VendorItemTerm, VendorItemTermUpdateRequest>(
    `${VENDORS}/${vendorId}/terms/${termId}`,
    body,
  );
}

export function deleteVendorTerm(vendorId: string, termId: string): Promise<void> {
  return apiDelete(`${VENDORS}/${vendorId}/terms/${termId}`);
}
