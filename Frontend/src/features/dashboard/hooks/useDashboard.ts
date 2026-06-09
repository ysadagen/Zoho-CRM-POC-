/**
 * React Query hooks for the dashboard. Each card subscribes to the hook(s) it
 * needs; React Query dedupes the shared `items` query across cards so the
 * catalog is fetched once per render. Read queries inherit the app defaults
 * (retry ×2) from the QueryClient.
 */
import { useQuery, type UseQueryResult } from '@tanstack/react-query';

import type { Item, StockMovement } from '@/types/api.types';

import {
  fetchDashboardItems,
  fetchDraftPurchaseOrderCount,
  fetchDraftSalesOrderCount,
  fetchRecentMovements,
} from '../api/dashboard.api';

export const dashboardKeys = {
  all: ['dashboard'] as const,
  items: ['dashboard', 'items'] as const,
  movements: ['dashboard', 'movements'] as const,
  draftPoCount: ['dashboard', 'po-draft-count'] as const,
  draftSoCount: ['dashboard', 'so-draft-count'] as const,
};

export function useDashboardItems(): UseQueryResult<Item[]> {
  return useQuery({ queryKey: dashboardKeys.items, queryFn: fetchDashboardItems });
}

export function useRecentMovements(): UseQueryResult<StockMovement[]> {
  return useQuery({ queryKey: dashboardKeys.movements, queryFn: fetchRecentMovements });
}

export function useDraftPoCount(): UseQueryResult<number> {
  return useQuery({ queryKey: dashboardKeys.draftPoCount, queryFn: fetchDraftPurchaseOrderCount });
}

export function useDraftSoCount(): UseQueryResult<number> {
  return useQuery({ queryKey: dashboardKeys.draftSoCount, queryFn: fetchDraftSalesOrderCount });
}
