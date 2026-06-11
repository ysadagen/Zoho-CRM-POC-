import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import { clearSession } from '@/auth/token-storage';
import { renderWithProviders, seedSession } from '@/test/utils';

import { DashboardPage } from './DashboardPage';

const BASE = 'http://localhost:8000/api/v1';
const emptyList = () => HttpResponse.json({ items: [], total: 0, limit: 100, offset: 0 });

let itemCalls = 0;
const server = setupServer(
  http.get(`${BASE}/items`, () => {
    itemCalls += 1;
    return emptyList();
  }),
  http.get(`${BASE}/stock-movements`, emptyList),
  http.get(`${BASE}/purchase-orders`, emptyList),
  http.get(`${BASE}/sales-orders`, emptyList),
);

beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }));
afterEach(() => {
  server.resetHandlers();
  clearSession();
  itemCalls = 0;
});
afterAll(() => server.close());

describe('DashboardPage', () => {
  it('greets the signed-in user by first name', async () => {
    seedSession();
    renderWithProviders(<DashboardPage />);
    expect(
      await screen.findByText(/Good (morning|afternoon|evening), Ravi/),
    ).toBeInTheDocument();
  });

  it('splits New Order into sales and purchase options', async () => {
    seedSession();
    renderWithProviders(<DashboardPage />);
    await screen.findByText('Total Stock Value');

    await userEvent.click(screen.getByRole('button', { name: /create a new order/i }));

    expect(screen.getByRole('menuitem', { name: 'New Sales Order' })).toHaveAttribute(
      'href',
      '/sales-orders/new',
    );
    expect(screen.getByRole('menuitem', { name: 'New Purchase Order' })).toHaveAttribute(
      'href',
      '/purchase-orders/new',
    );
  });

  it('refetches the dashboard queries when Refresh is clicked', async () => {
    seedSession();
    renderWithProviders(<DashboardPage />);

    await screen.findByText('Total Stock Value');
    const callsAfterLoad = itemCalls;

    await userEvent.click(screen.getByRole('button', { name: /refresh/i }));

    await waitFor(() => expect(itemCalls).toBeGreaterThan(callsAfterLoad));
  });
});
