import { apiGet, apiPost } from '@/lib/api/client';
import type { Paginated, SalesOrder, SalesOrderCreateRequest } from '@/types/api.types';
import type { SalesOrderStatus } from '@/types/enums';

const SALES_ORDERS = '/api/v1/sales-orders';

export interface ListSalesOrdersParams {
  limit: number;
  offset: number;
  status?: SalesOrderStatus;
  customer_id?: string;
}

function listQuery(params: ListSalesOrdersParams): Record<string, string | number> {
  const query: Record<string, string | number> = { limit: params.limit, offset: params.offset };
  if (params.status) query.status = params.status;
  if (params.customer_id) query.customer_id = params.customer_id;
  return query;
}

export function listSalesOrders(params: ListSalesOrdersParams): Promise<Paginated<SalesOrder>> {
  return apiGet<Paginated<SalesOrder>>(SALES_ORDERS, { params: listQuery(params) });
}

export function getSalesOrder(id: string): Promise<SalesOrder> {
  return apiGet<SalesOrder>(`${SALES_ORDERS}/${id}`);
}

export function createSalesOrder(body: SalesOrderCreateRequest): Promise<SalesOrder> {
  return apiPost<SalesOrder, SalesOrderCreateRequest>(SALES_ORDERS, body);
}

/** Atomically ships a DRAFT SO (stock OUT). 409 SO_NOT_DRAFT / INSUFFICIENT_STOCK. */
export function shipSalesOrder(id: string): Promise<SalesOrder> {
  return apiPost<SalesOrder>(`${SALES_ORDERS}/${id}/ship`);
}
