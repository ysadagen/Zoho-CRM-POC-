import { apiGet, apiPatch, apiPost } from '@/lib/api/client';
import type {
  Customer,
  CustomerCreateRequest,
  CustomerUpdateRequest,
  Paginated,
  SalesOrder,
} from '@/types/api.types';

const CUSTOMERS = '/api/v1/customers';
const SALES_ORDERS = '/api/v1/sales-orders';

export interface ListCustomersParams {
  limit: number;
  offset: number;
  search?: string;
}

/** Minimal subset the POST is guaranteed to return (id + name) — safe to read. */
export interface CustomerCreated {
  id: string;
  company_name: string;
}

function listQuery(params: ListCustomersParams): Record<string, string | number> {
  const query: Record<string, string | number> = { limit: params.limit, offset: params.offset };
  const search = params.search?.trim();
  if (search) query.search = search;
  return query;
}

export function listCustomers(params: ListCustomersParams): Promise<Paginated<Customer>> {
  return apiGet<Paginated<Customer>>(CUSTOMERS, { params: listQuery(params) });
}

export function getCustomer(id: string): Promise<Customer> {
  return apiGet<Customer>(`${CUSTOMERS}/${id}`);
}

export function createCustomer(body: CustomerCreateRequest): Promise<CustomerCreated> {
  return apiPost<CustomerCreated, CustomerCreateRequest>(CUSTOMERS, body);
}

export function updateCustomer(id: string, body: CustomerUpdateRequest): Promise<Customer> {
  return apiPatch<Customer, CustomerUpdateRequest>(`${CUSTOMERS}/${id}`, body);
}

/** Sales orders placed by one customer — the detail "Sales orders" tab. */
export function listCustomerSalesOrders(
  customerId: string,
  limit = 50,
): Promise<Paginated<SalesOrder>> {
  return apiGet<Paginated<SalesOrder>>(SALES_ORDERS, {
    params: { customer_id: customerId, limit },
  });
}
