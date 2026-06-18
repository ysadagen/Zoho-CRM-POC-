import { http, HttpResponse } from 'msw';

/**
 * MSW handlers for every read query the dashboard fires on mount.
 *
 * The dashboard loads the KPI/movement widgets *and* the Phase 2C intelligence
 * summary (hot leads, at-risk customers, lead funnel). Any test that lands on
 * the dashboard — directly or after login/navigation — must mock these so the
 * requests don't fall through to the real network and pollute the run.
 *
 * The Backend (`:8000`) owns the CRM/stock reads; the Intelligence service
 * (`:8002`) owns the scoring reads.
 */
const BACKEND = 'http://localhost:8000/api/v1';
const INTEL = 'http://localhost:8002/api/v1';

const emptyList = () => HttpResponse.json({ items: [], total: 0, limit: 100, offset: 0 });

export const dashboardHandlers = [
  http.get(`${BACKEND}/items`, emptyList),
  http.get(`${BACKEND}/stock-movements`, emptyList),
  http.get(`${BACKEND}/purchase-orders`, emptyList),
  http.get(`${BACKEND}/sales-orders`, emptyList),
  http.get(`${BACKEND}/leads`, emptyList),
  http.get(`${INTEL}/intelligence/lead-scores`, emptyList),
  http.get(`${INTEL}/intelligence/customer-health`, emptyList),
];
