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
  ActivityType,
  BatchStatus,
  CompetitiveRiskLevel,
  CustomerType,
  DealerPotential,
  DosageForm,
  DrugSchedule,
  EffortQuadrant,
  HealthClassification,
  ItemStatus,
  ItemType,
  LeadClassification,
  LeadSource,
  LeadStage,
  MaterialClassification,
  MovementDirection,
  MovementReason,
  MovementReferenceType,
  Pharmacopoeia,
  PurchaseOrderStatus,
  SalesOrderStatus,
  StorageCondition,
  VisitPriority,
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
  standard_cost: string | null;
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
  standard_cost?: string;
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
  standard_cost?: string;
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
  address: string | null;
  state: string | null;
  city: string | null;
  district: string | null;
  pincode: string | null;
  notes: string | null;
  customer_type: CustomerType;
  competitive_risk_level: CompetitiveRiskLevel;
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
  address?: string;
  state?: string;
  city?: string;
  district?: string;
  pincode?: string;
  notes?: string;
  customer_type?: CustomerType;
  competitive_risk_level?: CompetitiveRiskLevel;
}

export type CustomerUpdateRequest = Partial<CustomerCreateRequest> & {
  is_active?: boolean;
};

export interface CustomerTarget {
  id: string;
  customer_id: string;
  period_start: string;
  period_end: string;
  target_quantity: string;
  target_revenue: string | null;
  created_at: string;
  updated_at: string;
}

export interface CustomerTargetCreateRequest {
  period_start: string;
  period_end: string;
  target_quantity: string;
  target_revenue?: string;
}

export interface CustomerTargetUpdateRequest {
  period_start?: string;
  period_end?: string;
  target_quantity?: string;
  target_revenue?: string;
}

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
  address: string | null;
  notes: string | null;
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
  address?: string;
  notes?: string;
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

/* ============================================================
 *  Leads + activities (Backend 2A — http://localhost:8000)
 * ============================================================ */

export interface Lead {
  id: string;
  lead_number: string;
  stage: LeadStage;
  contact_name: string;
  source: LeadSource;
  assigned_to_user_id: string;
  customer_id: string | null;
  phone: string | null;
  email: string | null;
  item_id: string | null;
  quantity: string | null;
  estimated_budget: string | null;
  dealer_potential: DealerPotential | null;
  required_by_date: string | null;
  state: string | null;
  district: string | null;
  city: string | null;
  pincode: string | null;
  won_value: string | null;
  won_at: string | null;
  lost_at: string | null;
  lost_reason: string | null;
  notes: string | null;
  is_active: boolean;
  created_by_user_id: string;
  updated_by_user_id: string;
  created_at: string;
  updated_at: string;
}

export interface LeadStageHistoryEntry {
  id: string;
  from_stage: LeadStage | null;
  to_stage: LeadStage;
  changed_at: string;
  changed_by_user_id: string;
  remark: string | null;
}

export interface LeadDetail extends Lead {
  stage_history: LeadStageHistoryEntry[];
}

export interface LeadCreateRequest {
  contact_name: string;
  source: LeadSource;
  assigned_to_user_id: string;
  customer_id?: string;
  phone?: string;
  email?: string;
  item_id?: string;
  quantity?: string;
  estimated_budget?: string;
  dealer_potential?: DealerPotential;
  required_by_date?: string;
  state?: string;
  district?: string;
  city?: string;
  pincode?: string;
  notes?: string;
}

export type LeadUpdateRequest = Partial<LeadCreateRequest> & { is_active?: boolean };

export interface StageTransitionRequest {
  to_stage: LeadStage;
  remark?: string;
  won_value?: string;
  lost_reason?: string;
}

export interface Activity {
  id: string;
  type: ActivityType;
  rep_user_id: string;
  customer_id: string | null;
  lead_id: string | null;
  occurred_at: string;
  duration_minutes: number | null;
  remarks: string | null;
  created_by_user_id: string;
  created_at: string;
}

export interface ActivityCreateRequest {
  type: ActivityType;
  occurred_at: string;
  rep_user_id?: string;
  customer_id?: string;
  lead_id?: string;
  duration_minutes?: number;
  remarks?: string;
}

/* ============================================================
 *  Intelligence service score reads (http://localhost:8002)
 *  Read live; numeric scores arrive as JSON numbers (not Decimal strings).
 * ============================================================ */

export interface LeadScoreComponents {
  urgency: number;
  location: number;
  contribution_margin: number;
  quantity: number;
  product_margin: number;
}

export interface LeadScore {
  lead_id: string;
  config_version: number;
  computed_at: string;
  components: LeadScoreComponents;
  total_score: number;
  classification: LeadClassification;
  defaults_applied: string[];
}

export interface LeadScoreListItem extends LeadScore {
  lead_number: string;
  contact_name: string;
  assigned_to_user_id: string;
}

export interface LeadScoreList {
  items: LeadScoreListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface LeadScoreDetail extends LeadScore {
  history: LeadScore[];
}

export interface CustomerHealthCpsComponents {
  volume_achievement: number;
  payment_discipline: number;
  engagement: number;
  growth_trend: number;
  margin_quality: number;
}

export interface CustomerHealthCrsComponents {
  volume_decline: number;
  payment_risk: number;
  competitive_risk: number;
  engagement_gap: number;
  service_risk: number;
}

export interface CustomerHealth {
  customer_id: string;
  company_name: string;
  computed_at: string;
  weight_profile: string;
  cps: number;
  crs: number;
  cps_components: CustomerHealthCpsComponents;
  crs_components: CustomerHealthCrsComponents;
  health_score: number;
  classification: HealthClassification;
  defaults_applied: string[];
}

export interface CustomerHealthList {
  items: CustomerHealth[];
  total: number;
  limit: number;
  offset: number;
}

export interface CustomerHealthSnapshot {
  computed_at: string;
  cps: number;
  crs: number;
  health_score: number;
  classification: HealthClassification;
}

export interface CustomerHealthDetail extends CustomerHealth {
  history: CustomerHealthSnapshot[];
}

export interface EffortEfficiencyComponents {
  stage_change_rate: number;
  won_rate: number;
  revenue_efficiency: number;
  time_to_close: number;
  lead_score_utilization: number;
}

export interface EffortActivityCounts {
  visits: number;
  meetings: number;
  follow_ups: number;
  calls: number;
  hours_logged: number;
}

export interface EffortEfficiency {
  rep_user_id: string;
  rep_email: string;
  period_start: string;
  period_end: string;
  activity_counts: EffortActivityCounts;
  effort_raw: number;
  effort_score: number;
  efficiency_components: EffortEfficiencyComponents;
  efficiency_score: number;
  efficiency_band: string;
  quadrant: EffortQuadrant;
}

export interface EffortEfficiencyList {
  items: EffortEfficiency[];
  total: number;
  period_start: string;
  period_end: string;
}

export interface BeatCustomerBreakdown {
  revenue_score: number;
  visit_gap_score: number;
  customer_type_score: number;
  location_density_score: number;
}

export interface BeatCustomer {
  customer_id: string;
  company_name: string;
  district: string | null;
  customer_type: string;
  vps: number;
  priority: VisitPriority;
  breakdown: BeatCustomerBreakdown;
  days_since_last_visit: number | null;
  revenue_90d: string;
}

export interface BeatCluster {
  district: string;
  customer_count: number;
  lds: number;
  cluster_opportunity: boolean;
}

export interface BeatPlan {
  rep_user_id: string;
  generated_at: string;
  max_visits: number;
  clusters: BeatCluster[];
  suggested_beat: BeatCustomer[];
  all_customers: BeatCustomer[];
}
