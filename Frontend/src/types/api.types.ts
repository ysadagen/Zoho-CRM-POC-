/**
 * Typed mirrors of the Inventory Backend's Pydantic schemas.
 *
 * Authoritative contract: `Backend/docs/Backend_Reference.md`.
 * Numeric fields that the Backend returns as `Decimal` (e.g. `stock_quantity`,
 * `unit_price`, `subtotal`) come over the wire as JSON strings to preserve
 * precision. We keep them as `string` here and convert to `number` (or
 * `Number(...).toFixed(2)`) only at the formatter boundary.
 */

import type {
  ItemStatus,
  ItemType,
  MovementDirection,
  MovementReason,
  MovementReferenceType,
  PurchaseOrderStatus,
  SalesOrderStatus,
} from './enums';

/* ============================================================
 *  Generic envelopes
 * ============================================================ */

export interface Paginated<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface ApiErrorEnvelope {
  error: {
    code: string;
    message: string;
    request_id: string;
  };
}

/* ============================================================
 *  Auth / users
 * ============================================================ */

export interface User {
  id: string;
  email: string;
  full_name: string;
  is_admin: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: 'bearer';
  expires_in: number;
  user: User;
}

export interface RegisterRequest {
  email: string;
  full_name: string;
  password: string;
}

export interface UserUpdateRequest {
  full_name?: string;
  is_active?: boolean;
  is_admin?: boolean;
}

/* ============================================================
 *  Items
 * ============================================================ */

export interface Item {
  id: string;
  sku: string;
  name: string;
  description: string | null;
  type: ItemType;
  category: string | null;
  unit_of_measure: string;
  stock_quantity: string;
  reorder_threshold: string | null;
  unit_price: string;
  status: ItemStatus;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ItemCreateRequest {
  sku: string;
  name: string;
  description?: string;
  type: ItemType;
  category: string;
  unit_of_measure: string;
  stock_quantity?: string;
  reorder_threshold?: string;
  unit_price: string;
}

export interface ItemUpdateRequest {
  name?: string;
  description?: string;
  category?: string;
  unit_of_measure?: string;
  reorder_threshold?: string;
  unit_price?: string;
  is_active?: boolean;
}

/* ============================================================
 *  Customers
 * ============================================================ */

export interface Customer {
  id: string;
  company_name: string;
  contact_person: string | null;
  email: string | null;
  phone: string | null;
  customer_code: string | null;
  gstin: string | null;
  is_privileged: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CustomerCreateRequest {
  company_name: string;
  contact_person?: string;
  email?: string;
  phone?: string;
  customer_code?: string;
  gstin?: string;
  is_privileged?: boolean;
}

export type CustomerUpdateRequest = Partial<CustomerCreateRequest> & {
  is_active?: boolean;
};

/* ============================================================
 *  Vendors
 * ============================================================ */

export interface Vendor {
  id: string;
  vendor_name: string;
  contact_person: string | null;
  email: string | null;
  phone: string | null;
  vendor_code: string | null;
  gstin: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface VendorCreateRequest {
  vendor_name: string;
  contact_person?: string;
  email?: string;
  phone?: string;
  vendor_code?: string;
  gstin?: string;
}

export type VendorUpdateRequest = Partial<VendorCreateRequest> & {
  is_active?: boolean;
};

/* ============================================================
 *  Vendor item terms
 * ============================================================ */

export interface VendorItemTerm {
  id: string;
  vendor_id: string;
  item_id: string;
  rate: string;
  discount_percent: string;
  effective_from: string;
  effective_to: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface VendorItemTermCreateRequest {
  item_id: string;
  rate: string;
  discount_percent?: string;
  effective_from: string;
  effective_to?: string | null;
}

export type VendorItemTermUpdateRequest = Partial<
  Omit<VendorItemTermCreateRequest, 'item_id'>
> & { is_active?: boolean };

/* ============================================================
 *  Stock movements
 * ============================================================ */

export interface StockMovement {
  id: string;
  item_id: string;
  direction: MovementDirection;
  reason: MovementReason;
  quantity: string;
  signed_quantity: string;
  stock_before: string;
  stock_after: string;
  reference_type: MovementReferenceType | null;
  reference_id: string | null;
  remarks: string | null;
  created_by_user_id: string;
  created_at: string;
}

export interface ManualAdjustmentRequest {
  item_id: string;
  direction: MovementDirection;
  quantity: string;
  remarks: string;
}

/* ============================================================
 *  Purchase orders
 * ============================================================ */

export interface PurchaseOrderItem {
  id: string;
  purchase_order_id: string;
  item_id: string;
  quantity: string;
  unit_price: string;
  line_total: string;
  created_at: string;
}

export interface PurchaseOrder {
  id: string;
  po_number: string;
  vendor_id: string;
  order_date: string;
  expected_delivery_date: string | null;
  received_date: string | null;
  status: PurchaseOrderStatus;
  subtotal: string;
  total: string;
  notes: string | null;
  items: PurchaseOrderItem[];
  created_at: string;
  updated_at: string;
}

export interface PurchaseOrderCreateLine {
  item_id: string;
  quantity: string;
  unit_price?: string;
}

export interface PurchaseOrderCreateRequest {
  vendor_id: string;
  expected_delivery_date?: string;
  notes?: string;
  items: PurchaseOrderCreateLine[];
}

/* ============================================================
 *  Sales orders
 * ============================================================ */

export interface SalesOrderItem {
  id: string;
  sales_order_id: string;
  item_id: string;
  quantity: string;
  unit_price: string;
  line_total: string;
  created_at: string;
}

export interface SalesOrder {
  id: string;
  so_number: string;
  customer_id: string;
  order_date: string;
  expected_delivery_date: string | null;
  shipped_date: string | null;
  status: SalesOrderStatus;
  subtotal: string;
  total: string;
  notes: string | null;
  items: SalesOrderItem[];
  created_at: string;
  updated_at: string;
}

export interface SalesOrderCreateLine {
  item_id: string;
  quantity: string;
  unit_price?: string;
}

export interface SalesOrderCreateRequest {
  customer_id: string;
  expected_delivery_date?: string;
  notes?: string;
  items: SalesOrderCreateLine[];
}
