import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import { renderWithProviders } from '@/test/utils';

import { CustomerHealthPage } from './CustomerHealthPage';

const BASE = 'http://localhost:8002/api/v1';
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const ROW = {
  customer_id: 'c1',
  company_name: 'Acme Distributors',
  computed_at: '2026-06-01T00:00:00Z',
  weight_profile: 'default',
  cps: 72,
  crs: 18,
  cps_components: {
    volume_achievement: 20,
    payment_discipline: 18,
    engagement: 14,
    growth_trend: 12,
    margin_quality: 8,
  },
  crs_components: {
    volume_decline: 4,
    payment_risk: 5,
    competitive_risk: 3,
    engagement_gap: 4,
    service_risk: 2,
  },
  health_score: 54,
  classification: 'AT_RISK',
  defaults_applied: ['engagement'],
};

function listOk(params?: { total?: number; limit?: number; offset?: number }) {
  return http.get(`${BASE}/intelligence/customer-health`, () =>
    HttpResponse.json({
      items: [ROW],
      total: params?.total ?? 1,
      limit: params?.limit ?? 25,
      offset: params?.offset ?? 0,
    }),
  );
}

function detailOk() {
  return http.get(`${BASE}/intelligence/customer-health/c1`, () =>
    HttpResponse.json({ ...ROW, history: [] }),
  );
}

describe('CustomerHealthPage', () => {
  it('lists customers from the Intelligence endpoint', async () => {
    server.use(listOk());
    renderWithProviders(<CustomerHealthPage />);
    const row = (await screen.findByText('Acme Distributors')).closest('tr');
    expect(row).not.toBeNull();
    // "At Risk" also appears as a filter option, so scope to the row's badge.
    expect(within(row as HTMLElement).getByText('At Risk')).toBeInTheDocument();
  });

  it('opens the drawer and shows the CPS/CRS breakdown', async () => {
    server.use(listOk(), detailOk());
    const user = userEvent.setup();
    renderWithProviders(<CustomerHealthPage />);

    await user.click(await screen.findByText('Acme Distributors'));

    expect(
      await screen.findByText('Customer Performance Score (CPS)'),
    ).toBeInTheDocument();
    expect(screen.getByText('Customer Risk Score (CRS)')).toBeInTheDocument();
    expect(screen.getByText('Volume achievement')).toBeInTheDocument();
    expect(screen.getByText('Competitive risk')).toBeInTheDocument();
    expect(screen.getByText(/Defaults applied: engagement/)).toBeInTheDocument();
  });

  it('shows a page error with the Request ID on failure', async () => {
    server.use(
      http.get(`${BASE}/intelligence/customer-health`, () =>
        HttpResponse.json(
          { error: { code: 'UNKNOWN_ERROR', message: 'Boom', request_id: 'req-ch' } },
          { status: 500 },
        ),
      ),
    );
    renderWithProviders(<CustomerHealthPage />);
    expect(await screen.findByText('Something went wrong')).toBeInTheDocument();
    expect(screen.getByText(/Request ID: req-ch/)).toBeInTheDocument();
  });

  it('does not show pagination when total fits on one page', async () => {
    server.use(listOk({ total: 1 }));
    renderWithProviders(<CustomerHealthPage />);
    await screen.findByText('Acme Distributors');
    expect(screen.queryByRole('navigation', { name: 'Pagination' })).toBeNull();
  });

  it('shows pagination controls and navigates when total exceeds page size', async () => {
    let capturedOffset = '0';
    server.use(
      http.get(`${BASE}/intelligence/customer-health`, ({ request }) => {
        capturedOffset = new URL(request.url).searchParams.get('offset') ?? '0';
        return HttpResponse.json({ items: [ROW], total: 50, limit: 25, offset: Number(capturedOffset) });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<CustomerHealthPage />);
    await screen.findByText('Acme Distributors');

    const nav = screen.getByRole('navigation', { name: 'Pagination' });
    expect(nav).toBeInTheDocument();

    const nextBtn = screen.getByRole('button', { name: 'Next page' });
    expect(screen.getByRole('button', { name: 'Previous page' })).toBeDisabled();
    expect(nextBtn).not.toBeDisabled();

    await user.click(nextBtn);
    expect(capturedOffset).toBe('25');
  });

  it('resets to page 1 when the classification filter changes', async () => {
    const offsets: string[] = [];
    server.use(
      http.get(`${BASE}/intelligence/customer-health`, ({ request }) => {
        offsets.push(new URL(request.url).searchParams.get('offset') ?? '0');
        return HttpResponse.json({ items: [ROW], total: 50, limit: 25, offset: 0 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<CustomerHealthPage />);
    await screen.findByText('Acme Distributors');

    // Navigate to page 2
    await user.click(screen.getByRole('button', { name: 'Next page' }));
    // Change filter — offset must reset to 0
    await user.click(screen.getByRole('tab', { name: 'Healthy' }));

    const lastOffset = offsets[offsets.length - 1];
    expect(lastOffset).toBe('0');
  });
});
