import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { setupServer } from 'msw/node';
import { http, HttpResponse, delay } from 'msw';

import { renderWithProviders } from '@/test/utils';

import { SyncZohoKpiCard } from './SyncZohoKpiCard';

const URL = 'http://localhost:8000/api/v1/crm/trigger-ingest';
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function syncButton(): HTMLButtonElement {
  return screen.getByRole('button', { name: /sync from zoho crm/i }) as HTMLButtonElement;
}

describe('SyncZohoKpiCard', () => {
  it('starts idle with the sync glyph and an accessible label', () => {
    renderWithProviders(<SyncZohoKpiCard />);
    const btn = syncButton();
    expect(btn).toHaveAttribute('data-sync-state', 'idle');
    expect(btn).not.toBeDisabled();
    expect(screen.getByText('Not synced')).toBeInTheDocument();
    // Idle glyph carries no motion class.
    expect(btn.querySelector('.kpi-spin, .kpi-sync-pop, .kpi-sync-shake')).toBeNull();
  });

  it('enters the syncing state — disabled with a spinning glyph — while in flight', async () => {
    server.use(
      http.post(URL, async () => {
        await delay(80);
        return HttpResponse.json({ ok: true });
      }),
    );
    renderWithProviders(<SyncZohoKpiCard />);

    await userEvent.click(syncButton());

    expect(syncButton()).toHaveAttribute('data-sync-state', 'syncing');
    expect(syncButton()).toBeDisabled();
    expect(syncButton().querySelector('.kpi-spin')).not.toBeNull();

    await waitFor(() => expect(syncButton()).toHaveAttribute('data-sync-state', 'ok'));
  });

  it('morphs to the success checkmark (pop) on an ok response', async () => {
    server.use(http.post(URL, () => HttpResponse.json({ ok: true })));
    renderWithProviders(<SyncZohoKpiCard />);

    await userEvent.click(syncButton());

    await waitFor(() => expect(syncButton()).toHaveAttribute('data-sync-state', 'ok'));
    expect(screen.getByText('Connected')).toBeInTheDocument();
    expect(syncButton().querySelector('.kpi-sync-pop')).not.toBeNull();
  });

  it('morphs to the error glyph (shake) on a non-ok response', async () => {
    server.use(http.post(URL, () => HttpResponse.json({ ok: false })));
    renderWithProviders(<SyncZohoKpiCard />);

    await userEvent.click(syncButton());

    await waitFor(() => expect(syncButton()).toHaveAttribute('data-sync-state', 'error'));
    expect(screen.getByText('Sync failed')).toBeInTheDocument();
    expect(syncButton().querySelector('.kpi-sync-shake')).not.toBeNull();
  });

  it('surfaces the error state and the Request ID when the network call fails', async () => {
    server.use(
      http.post(URL, () =>
        HttpResponse.json(
          { error: { code: 'UNKNOWN_ERROR', message: 'Boom', request_id: 'req-zoho-1' } },
          { status: 500 },
        ),
      ),
    );
    renderWithProviders(<SyncZohoKpiCard />);

    await userEvent.click(syncButton());

    await waitFor(() => expect(syncButton()).toHaveAttribute('data-sync-state', 'error'));
    // §5.6 — the danger toast carries the correlating Request ID.
    expect(await screen.findByText('req-zoho-1')).toBeInTheDocument();
  });

  it('ignores extra clicks while a sync is already running', async () => {
    let calls = 0;
    server.use(
      // Never resolves — keeps the request in flight so the button stays disabled.
      http.post(URL, () => {
        calls += 1;
        return new Promise<HttpResponse>(() => {});
      }),
    );
    renderWithProviders(<SyncZohoKpiCard />);

    await userEvent.click(syncButton());
    await waitFor(() => expect(syncButton()).toBeDisabled());
    // A second click on the disabled button must not fire another request.
    await userEvent.click(syncButton());

    expect(calls).toBe(1);
  });
});
