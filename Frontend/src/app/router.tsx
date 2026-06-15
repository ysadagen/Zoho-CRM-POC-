import { Navigate, Route, Routes } from 'react-router-dom';

import { ProtectedRoute } from '@/auth/ProtectedRoute';
import { NotFoundPage } from '@/components/NotFoundPage';
import { AppShell } from '@/components/layout/AppShell';
import { AuthShell } from '@/components/layout/AuthShell';
import { LoginPage } from '@/features/auth/pages/LoginPage';
import { RegisterPage } from '@/features/auth/pages/RegisterPage';
import { DashboardPage } from '@/features/dashboard/pages/DashboardPage';
import { CustomerDetailPage } from '@/features/customers/pages/CustomerDetailPage';
import { CustomersListPage } from '@/features/customers/pages/CustomersListPage';
import { VendorDetailPage } from '@/features/vendors/pages/VendorDetailPage';
import { VendorsListPage } from '@/features/vendors/pages/VendorsListPage';
import { ItemDetailPage } from '@/features/items/pages/ItemDetailPage';
import { ItemsListPage } from '@/features/items/pages/ItemsListPage';
import { PurchaseOrderCreatePage } from '@/features/purchase-orders/pages/PurchaseOrderCreatePage';
import { PurchaseOrderDetailPage } from '@/features/purchase-orders/pages/PurchaseOrderDetailPage';
import { PurchaseOrdersListPage } from '@/features/purchase-orders/pages/PurchaseOrdersListPage';
import { SalesOrderCreatePage } from '@/features/sales-orders/pages/SalesOrderCreatePage';
import { SalesOrderDetailPage } from '@/features/sales-orders/pages/SalesOrderDetailPage';
import { SalesOrdersListPage } from '@/features/sales-orders/pages/SalesOrdersListPage';
import { BatchesListPage } from '@/features/batches/pages/BatchesListPage';
import { StockMovementsListPage } from '@/features/stock-movements/pages/StockMovementsListPage';
import { SettingsPage } from '@/features/settings/pages/SettingsPage';

import { routes } from './routes';

/**
 * Route table. Public auth pages render in the {@link AuthShell}; everything
 * else is gated by {@link ProtectedRoute} and renders inside the {@link AppShell}.
 */
export function AppRouter(): JSX.Element {
  return (
    <Routes>
      <Route element={<AuthShell />}>
        <Route path={routes.login} element={<LoginPage />} />
        <Route path={routes.register} element={<RegisterPage />} />
      </Route>

      <Route element={<ProtectedRoute />}>
        <Route element={<AppShell />}>
          <Route path="/" element={<Navigate to={routes.dashboard} replace />} />
          <Route path={routes.dashboard} element={<DashboardPage />} />
          <Route path={routes.items} element={<ItemsListPage />} />
          <Route path={`${routes.items}/:id`} element={<ItemDetailPage />} />
          <Route path={routes.customers} element={<CustomersListPage />} />
          <Route path={`${routes.customers}/:id`} element={<CustomerDetailPage />} />
          <Route path={routes.vendors} element={<VendorsListPage />} />
          <Route path={`${routes.vendors}/:id`} element={<VendorDetailPage />} />
          <Route path={routes.purchaseOrders} element={<PurchaseOrdersListPage />} />
          <Route path={`${routes.purchaseOrders}/new`} element={<PurchaseOrderCreatePage />} />
          <Route path={`${routes.purchaseOrders}/:id`} element={<PurchaseOrderDetailPage />} />
          <Route path={routes.salesOrders} element={<SalesOrdersListPage />} />
          <Route path={`${routes.salesOrders}/new`} element={<SalesOrderCreatePage />} />
          <Route path={`${routes.salesOrders}/:id`} element={<SalesOrderDetailPage />} />
          <Route path={routes.batches} element={<BatchesListPage />} />
          <Route path={routes.stockMovements} element={<StockMovementsListPage />} />
          <Route path={routes.settings} element={<SettingsPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Route>
    </Routes>
  );
}
