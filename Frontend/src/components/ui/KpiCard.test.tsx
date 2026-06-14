import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { KpiCard } from './KpiCard';

describe('KpiCard', () => {
  it('renders label, value, and a tone-coloured delta', () => {
    const { container } = render(
      <KpiCard
        tone="accent"
        icon="package"
        label="Total Stock Value"
        value="₹ 24,58,750"
        delta="▲ 12.5% vs last month"
        deltaDir="up"
      />,
    );

    expect(screen.getByText('Total Stock Value')).toBeInTheDocument();
    expect(screen.getByText('₹ 24,58,750')).toBeInTheDocument();
    expect(screen.getByText('▲ 12.5% vs last month')).toHaveClass('delta', 'up');
    expect(container.firstChild).toHaveClass('kpi', 'accent');
  });

  it('omits the delta line when no delta is given', () => {
    const { container } = render(
      <KpiCard icon="cart" label="Open POs" value="12" />,
    );
    expect(container.querySelector('.delta')).toBeNull();
    // default tone adds no modifier class
    expect(container.firstChild).toHaveClass('kpi');
    expect(container.firstChild).not.toHaveClass('default');
  });
});
