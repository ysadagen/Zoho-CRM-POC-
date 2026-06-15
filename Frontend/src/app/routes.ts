/**
 * Route path constants — the single source of truth for URLs. Import these
 * instead of hard-coding path strings, so a route rename is a one-line change.
 */
export const routes = {
  dashboard: '/dashboard',
  items: '/items',
  salesOrders: '/sales-orders',
  purchaseOrders: '/purchase-orders',
  customers: '/customers',
  vendors: '/vendors',
  batches: '/batches',
  stockMovements: '/stock-movements',
  settings: '/settings',
  login: '/login',
  register: '/register',
} as const;
