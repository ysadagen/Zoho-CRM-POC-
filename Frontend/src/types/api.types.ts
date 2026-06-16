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
  BatchStatus,
  DosageForm,
  DrugSchedule,
  ItemStatus,
  ItemType,
  MaterialClassification,
  MovementDirection,
  MovementReason,
  MovementReferenceType,
  Pharmacopoeia,
  PurchaseOrderStatus,
  SalesOrderStatus,
  StorageCondition,
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

/** RAW-specific attributes (1:1 with the item). Null fields = unset. */
export interface RawItemDetail {
  material_classification: MaterialClassification | null;
  pharmacopoeia: Pharmacopoeia | null;
  is_hazardous: boolean;
}

/** FINISHED-product-specific attributes (1:1 with the item). */
export interface FinishedItemDetail {
  generic_name: string | null;
  brand_name: string | null;
  strength: string | null;
  dosage_form: DosageForm | null;
  pack_size: string | null;
  ingredients: string | null;
  container_specification: string | null;
  selling_price: string | null;
  license_number: string | null;
  registration_code: string | null;
  mrp: string | null;
  drug_schedule: DrugSchedule | null;
  is_prescription_required: boolean;
}

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
  storage_condition: StorageCondition | null;
  shelf_life_days: number | null;
  status: ItemStatus;
  is_active: boolean;
  /** Exactly one is populated, matching `type` (the other is null). */
  raw_detail: RawItemDetail | null;
  finished_detail: FinishedItemDetail | null;
  created_at: string;
  updated_at: string;
}

/** Detail blocks on create/patch — every field optional (partial-patch). */
export type RawItemDetailInput = Partial<RawItemDetail>;
export type FinishedItemDetailInput = Partial<FinishedItemDetail>;

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
  storage_condition?: StorageCondition;
  shelf_life_days?: number;
  raw_detail?: RawItemDetailInput;
  finished_detail?: FinishedItemDetailInput;
}

export interface ItemUpdateRequest {
  name?: string;
  description?: string;
  category?: string;
  unit_of_measure?: string;
  reorder_threshold?: string;
  unit_price?: string;
  storage_condition?: StorageCondition;
  shelf_life_days?: number;
  raw_detail?: RawItemDetailInput;
  finished_detail?: FinishedItemDetailInput;
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
  /** The physical lot this movement touched (PO receive / SO ship); null otherwise. */
  batch_id: string | null;
  remarks: string | null;
  created_by_user_id: string;
  created_at: string;
}

export interface ManualAdjustmentRequest {
  item_id: string;
  direction: MovementDirection;
  quantity: string;
  remarks: string;
  /** Optional lot to adjust; when set the lot quantity moves too (#8). */
  batch_id?: string;
}

/* ============================================================
 *  Batches (pharma — lots)
 * ============================================================ */

export interface Batch {
  id: string;
  item_id: string;
  batch_number: string;
  batch_status: BatchStatus;
  batch_received_date: string | null;
  manufacturing_date: string | null;
  expiry_date: string;
  quantity: string;
  initial_quantity: string;
  unit_cost: string | null;
  storage_location: string | null;
  vendor_id: string | null;
  received_via_po_id: string | null;
  /** Computed by the Backend: expiry_date < today. */
  is_expired: boolean;
  created_by_user_id: string;
  updated_by_user_id: string;
  created_at: string;
  updated_at: string;
}

/** Opening-balance lot creation (POST /batches). */
export interface BatchCreateRequest {
  item_id: string;
  batch_number: string;
  expiry_date: string;
  manufacturing_date?: string;
  quantity: string;
  unit_cost?: string;
  storage_location?: string;
  batch_status?: BatchStatus;
  batch_received_date?: string;
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

/**
 * One lot's details supplied at receive time, matched to a PO line by
 * item_id. A line may be split across several lots — when it is, every lot
 * carries a `quantity` and the lots' quantities sum to the PO line quantity.
 * A single lot may omit `quantity` (the whole line quantity is used).
 */
export interface PurchaseOrderReceiveLine {
  item_id: string;
  batch_number: string;
  expiry_date: string;
  manufacturing_date?: string;
  storage_location?: string;
  quantity?: string;
}

export interface PurchaseOrderReceiveRequest {
  lines: PurchaseOrderReceiveLine[];
}

/* ============================================================
 *  Sales orders
 * ============================================================ */

export interface SalesOrderItem {
  id: string;
  sales_order_id: string;
  item_id: string;
  /** Operator-chosen lot to ship this line from; null = First-Expiry-First-Out (#9). */
  batch_id: string | null;
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
  /** Optional lot to ship from; omit to let the Backend pick FEFO (#9). */
  batch_id?: string;
}

export interface SalesOrderCreateRequest {
  customer_id: string;
  expected_delivery_date?: string;
  notes?: string;
  items: SalesOrderCreateLine[];
}
