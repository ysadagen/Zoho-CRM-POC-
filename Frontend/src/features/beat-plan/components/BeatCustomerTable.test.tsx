import { describe, it, expect } from 'vitest';
import { render, screen, within } from '@testing-library/react';

import type { BeatCustomer } from '@/types/api.types';

import { BeatCustomerTable } from './BeatCustomerTable';

function customer(overrides: Partial<BeatCustomer> = {}): BeatCustomer {
  return {
    customer_id: 'cust-1',
    company_name: 'Acme Distributors',
    district: 'Raigarh',
    customer_type: 'DEALER',
    vps: 82,
    priority: 'CRITICAL',
    breakdown: {
      revenue_score: 30,
      visit_gap_score: 25,
      customer_type_score: 15,
      location_density_score: 12,
    },
    days_since_last_visit: 45,
    revenue_90d: '125000.00',
    ...overrides,
  };
}

describe('BeatCustomerTable', () => {
  it('renders a row with the priority badge', () => {
    render(<BeatCustomerTable customers={[customer()]} />);
    expect(screen.getByText('Acme Distributors')).toBeInTheDocument();
    expect(screen.getByText('Critical')).toBeInTheDocument();
    expect(screen.getByText('Raigarh')).toBeInTheDocument();
  });

  it('flags rows in the suggested beat', () => {
    const rows = [
      customer({ customer_id: 'cust-1', company_name: 'In Beat Co' }),
      customer({ customer_id: 'cust-2', company_name: 'Not In Beat Co' }),
    ];
    render(
      <BeatCustomerTable customers={rows} suggestedIds={new Set(['cust-1'])} />,
    );

    const inBeatRow = screen.getByText('In Beat Co').closest('tr');
    const otherRow = screen.getByText('Not In Beat Co').closest('tr');
    expect(inBeatRow).not.toBeNull();
    expect(otherRow).not.toBeNull();
    expect(within(inBeatRow as HTMLElement).getByText('In beat')).toBeInTheDocument();
    expect(within(otherRow as HTMLElement).queryByText('In beat')).toBeNull();
  });

  it('shows an empty state when there are no customers', () => {
    render(<BeatCustomerTable customers={[]} />);
    expect(screen.getByText('No customers to plan')).toBeInTheDocument();
  });
});
