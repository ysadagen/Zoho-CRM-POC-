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
