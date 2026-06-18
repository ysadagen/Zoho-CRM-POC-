import { routes } from '@/app/routes';
import type { IconName } from '@/components/ui/Icon';

export interface NavItem {
  to: string;
  label: string;
  icon: IconName;
}

/** The top-level destinations (UI_SPECIFICATION.md §3 + pharma Batches), in nav order. */
export const NAV_ITEMS: NavItem[] = [
  { to: routes.dashboard, label: 'Dashboard', icon: 'home' },
  { to: routes.items, label: 'Items', icon: 'box' },
  { to: routes.salesOrders, label: 'Sales Orders', icon: 'bag' },
  { to: routes.purchaseOrders, label: 'Purchase Orders', icon: 'cart' },
  { to: routes.customers, label: 'Customers', icon: 'user' },
  { to: routes.vendors, label: 'Vendors', icon: 'truck' },
  { to: routes.batches, label: 'Batches', icon: 'package' },
  { to: routes.stockMovements, label: 'Stock Movements', icon: 'swap' },
  { to: routes.settings, label: 'Settings', icon: 'cog' },
];

/** Resolve the active nav item for a pathname (exact or nested match). */
export function navItemForPath(pathname: string): NavItem | undefined {
  return NAV_ITEMS.find(
    (item) => pathname === item.to || pathname.startsWith(`${item.to}/`),
  );
}
