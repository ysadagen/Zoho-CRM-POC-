import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useLocation } from 'react-router-dom';
import { setupServer } from 'msw/node';
import { http, HttpResponse, type RequestHandler } from 'msw';

import { renderWithProviders } from '@/test/utils';

import { GlobalSearch } from './GlobalSearch';

const API = 'http://localhost:8000/api/v1';
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function LocationProbe(): JSX.Element {
  const { pathname } = useLocation();
  return <div data-testid="loc">{pathname}</div>;
}

const page = <T,>(items: T[]) => ({ items, total: items.length, limit: 5, offset: 0 });

/** Default: one hit per source. */
function handlers(): RequestHandler[] {
  return [
    http.get(`${API}/customers`, () =>
      HttpResponse.json(
        page([{ id: 'c1', company_name: 'Acme Corp', customer_code: 'CUST-1', city: 'Pune', email: null }]),
      ),
    ),
    http.get(`${API}/items`, () =>
      HttpResponse.json(page([{ id: 'i1', name: 'Acme Bottle 500ml', sku: 'SKU-1' }])),
    ),
    http.get(`${API}/vendors`, () =>
      HttpResponse.json(page([{ id: 'v1', vendor_name: 'Acme Supplies', vendor_code: 'VEN-1', email: null }])),
    ),
  ];
}

function emptyHandlers(): RequestHandler[] {
  return [
    http.get(`${API}/customers`, () => HttpResponse.json(page([]))),
    http.get(`${API}/items`, () => HttpResponse.json(page([]))),
    http.get(`${API}/vendors`, () => HttpResponse.json(page([]))),
  ];
}

async function openAndType(user: ReturnType<typeof userEvent.setup>, text: string): Promise<void> {
  await user.click(screen.getByRole('button', { name: /search \(ctrl or cmd k\)/i }));
  const input = await screen.findByRole('textbox', { name: /search customers/i });
  await user.type(input, text);
}

describe('GlobalSearch', () => {
  it('opens on Ctrl/Cmd+K and closes on Escape', async () => {
    const user = userEvent.setup();
    renderWithProviders(<GlobalSearch />);

    expect(screen.queryByRole('dialog')).toBeNull();
    await user.keyboard('{Control>}k{/Control}');
    expect(await screen.findByRole('dialog')).toBeInTheDocument();

    await user.keyboard('{Escape}');
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
  });

  it('opens when the Topbar trigger is clicked', async () => {
    const user = userEvent.setup();
    renderWithProviders(<GlobalSearch />);
    await user.click(screen.getByRole('button', { name: /search \(ctrl or cmd k\)/i }));
    expect(await screen.findByRole('dialog')).toBeInTheDocument();
  });

  it('prompts before the minimum query length, then shows grouped results', async () => {
    server.use(...handlers());
    const user = userEvent.setup();
    renderWithProviders(<GlobalSearch />);

    await user.click(screen.getByRole('button', { name: /search \(ctrl or cmd k\)/i }));
    // One char → still the prompt, no fetch.
    await user.type(await screen.findByRole('textbox', { name: /search customers/i }), 'a');
    expect(screen.getByText(/type at least 2 characters/i)).toBeInTheDocument();

    // Second char crosses the threshold and the three groups resolve.
    await user.keyboard('c');
    expect(await screen.findByText('Acme Corp')).toBeInTheDocument();
    expect(screen.getByText('Acme Bottle 500ml')).toBeInTheDocument();
    expect(screen.getByText('Acme Supplies')).toBeInTheDocument();
    expect(screen.getByText('Customers')).toBeInTheDocument();
    expect(screen.getByText('Items')).toBeInTheDocument();
    expect(screen.getByText('Vendors')).toBeInTheDocument();
  });

  it('shows an empty state when nothing matches', async () => {
    server.use(...emptyHandlers());
    const user = userEvent.setup();
    renderWithProviders(<GlobalSearch />);
    await openAndType(user, 'zzz');
    expect(await screen.findByText(/no results for/i)).toBeInTheDocument();
  });

  it('navigates to a record and closes when a result is clicked', async () => {
    server.use(...handlers());
    const user = userEvent.setup();
    renderWithProviders(
      <>
        <GlobalSearch />
        <LocationProbe />
      </>,
    );
    await openAndType(user, 'ac');
    await user.click(await screen.findByText('Acme Corp'));

    await waitFor(() => expect(screen.getByTestId('loc')).toHaveTextContent('/customers/c1'));
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('moves the highlight with ArrowDown and opens it with Enter', async () => {
    server.use(...handlers());
    const user = userEvent.setup();
    renderWithProviders(
      <>
        <GlobalSearch />
        <LocationProbe />
      </>,
    );
    await openAndType(user, 'ac');
    await screen.findByText('Acme Corp'); // results in: [customer, item, vendor]

    // First result is highlighted by default; ArrowDown → the item; Enter opens it.
    await user.keyboard('{ArrowDown}{Enter}');
    await waitFor(() => expect(screen.getByTestId('loc')).toHaveTextContent('/items/i1'));
  });

  it('tolerates a failing source: shows the others and flags the failure', async () => {
    server.use(
      http.get(`${API}/customers`, () =>
        HttpResponse.json(
          page([{ id: 'c1', company_name: 'Acme Corp', customer_code: 'CUST-1', city: null, email: null }]),
        ),
      ),
      http.get(`${API}/items`, () =>
        HttpResponse.json(page([{ id: 'i1', name: 'Acme Bottle 500ml', sku: 'SKU-1' }])),
      ),
      http.get(`${API}/vendors`, () => new HttpResponse(null, { status: 500 })),
    );
    const user = userEvent.setup();
    renderWithProviders(<GlobalSearch />);
    await openAndType(user, 'ac');

    expect(await screen.findByText('Acme Corp')).toBeInTheDocument();
    expect(screen.getByText('Acme Bottle 500ml')).toBeInTheDocument();
    expect(screen.getByText(/couldn.t load vendors/i)).toBeInTheDocument();
  });
});
