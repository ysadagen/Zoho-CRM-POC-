/**
 * Domain enums — kept in sync with the Backend Pydantic enums.
 * Backend reference: `Backend/docs/Backend_Reference.md` §7.
 */

export const ItemType = {
  RAW: 'RAW',
  FINISHED: 'FINISHED',
} as const;
export type ItemType = (typeof ItemType)[keyof typeof ItemType];

export const ItemStatus = {
  IN_STOCK: 'IN_STOCK',
  LOW_STOCK: 'LOW_STOCK',
  NO_STOCK: 'NO_STOCK',
} as const;
export type ItemStatus = (typeof ItemStatus)[keyof typeof ItemStatus];

export const MovementDirection = {
  IN: 'IN',
  OUT: 'OUT',
} as const;
export type MovementDirection = (typeof MovementDirection)[keyof typeof MovementDirection];

export const MovementReason = {
  PURCHASE: 'PURCHASE',
  SALE: 'SALE',
  ADJUSTMENT: 'ADJUSTMENT',
} as const;
export type MovementReason = (typeof MovementReason)[keyof typeof MovementReason];

export const MovementReferenceType = {
  PURCHASE_ORDER: 'PURCHASE_ORDER',
  SALES_ORDER: 'SALES_ORDER',
} as const;
export type MovementReferenceType =
  (typeof MovementReferenceType)[keyof typeof MovementReferenceType];

export const PurchaseOrderStatus = {
  DRAFT: 'DRAFT',
  RECEIVED: 'RECEIVED',
} as const;
export type PurchaseOrderStatus =
  (typeof PurchaseOrderStatus)[keyof typeof PurchaseOrderStatus];

export const SalesOrderStatus = {
  DRAFT: 'DRAFT',
  SHIPPED: 'SHIPPED',
} as const;
export type SalesOrderStatus = (typeof SalesOrderStatus)[keyof typeof SalesOrderStatus];

/* ============================================================
 *  Pharma enums (Backend_Reference §7 — "Enum types (pharma)")
 * ============================================================ */

/** Required storage environment — a product-level property (on `items`). */
export const StorageCondition = {
  AMBIENT: 'AMBIENT',
  COLD_CHAIN_2_8: 'COLD_CHAIN_2_8',
  FROZEN: 'FROZEN',
  CONTROLLED: 'CONTROLLED',
} as const;
export type StorageCondition = (typeof StorageCondition)[keyof typeof StorageCondition];

/** RAW-material classification (`raw_item_details`). */
export const MaterialClassification = {
  API: 'API',
  EXCIPIENT: 'EXCIPIENT',
  SOLVENT: 'SOLVENT',
  REAGENT: 'REAGENT',
  PACKAGING: 'PACKAGING',
} as const;
export type MaterialClassification =
  (typeof MaterialClassification)[keyof typeof MaterialClassification];

/** Pharmacopoeia standard the raw material conforms to (`raw_item_details`). */
export const Pharmacopoeia = {
  IP: 'IP',
  BP: 'BP',
  USP: 'USP',
  EP: 'EP',
  JP: 'JP',
  NONE: 'NONE',
} as const;
export type Pharmacopoeia = (typeof Pharmacopoeia)[keyof typeof Pharmacopoeia];

/** Dosage form of a finished product (`finished_item_details`). */
export const DosageForm = {
  TABLET: 'TABLET',
  CAPSULE: 'CAPSULE',
  SYRUP: 'SYRUP',
  SUSPENSION: 'SUSPENSION',
  INJECTION: 'INJECTION',
  OINTMENT: 'OINTMENT',
  CREAM: 'CREAM',
  GEL: 'GEL',
  DROPS: 'DROPS',
  POWDER: 'POWDER',
  INHALER: 'INHALER',
  OTHER: 'OTHER',
} as const;
export type DosageForm = (typeof DosageForm)[keyof typeof DosageForm];

/** Regulatory schedule (controlled-substance class) (`finished_item_details`). */
export const DrugSchedule = {
  NONE: 'NONE',
  H: 'H',
  H1: 'H1',
  X: 'X',
} as const;
export type DrugSchedule = (typeof DrugSchedule)[keyof typeof DrugSchedule];

/** QC lifecycle state of a lot (`batches`). */
export const BatchStatus = {
  QUARANTINE: 'QUARANTINE',
  RELEASED: 'RELEASED',
  EXPIRED: 'EXPIRED',
  REJECTED: 'REJECTED',
  RECALLED: 'RECALLED',
} as const;
export type BatchStatus = (typeof BatchStatus)[keyof typeof BatchStatus];
