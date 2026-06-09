import { apiGet, apiPost } from '@/lib/api/client';
import type { Paginated, PurchaseOrder, PurchaseOrderCreateRequest } from '@/types/api.types';
import type { PurchaseOrderStatus } from '@/types/enums';

const PURCHASE_ORDERS = '/api/v1/purchase-orders';

export interface ListPurchaseOrdersParams {
  limit: number;
  offset: number;
  status?: PurchaseOrderStatus;
  vendor_id?: string;
}

function listQuery(params: ListPurchaseOrdersParams): Record<string, string | number> {
  const query: Record<string, string | number> = { limit: params.limit, offset: params.offset };
  if (params.status) query.status = params.status;
  if (params.vendor_id) query.vendor_id = params.vendor_id;
  return query;
}

export function listPurchaseOrders(params: ListPurchaseOrdersParams): Promise<Paginated<PurchaseOrder>> {
  return apiGet<Paginated<PurchaseOrder>>(PURCHASE_ORDERS, { params: listQuery(params) });
}

export function getPurchaseOrder(id: string): Promise<PurchaseOrder> {
  return apiGet<PurchaseOrder>(`${PURCHASE_ORDERS}/${id}`);
}

export function createPurchaseOrder(body: PurchaseOrderCreateRequest): Promise<PurchaseOrder> {
  return apiPost<PurchaseOrder, PurchaseOrderCreateRequest>(PURCHASE_ORDERS, body);
}

/** Atomically receives a DRAFT PO (stock IN). No body. 409 PO_NOT_DRAFT if not draft. */
export function receivePurchaseOrder(id: string): Promise<PurchaseOrder> {
  return apiPost<PurchaseOrder>(`${PURCHASE_ORDERS}/${id}/receive`);
}
