import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { Tabs } from './Tabs';

const TABS = [
  { value: 'overview', label: 'Overview' },
  { value: 'history', label: 'History' },
] as const;

describe('Tabs', () => {
  it('marks the active tab and reports changes', async () => {
    const onChange = vi.fn();
    render(<Tabs tabs={[...TABS]} value="overview" onChange={onChange} ariaLabel="Item tabs" />);

    expect(screen.getByRole('tab', { name: 'Overview' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tab', { name: 'History' })).toHaveAttribute('aria-selected', 'false');

    await userEvent.click(screen.getByRole('tab', { name: 'History' }));
    expect(onChange).toHaveBeenCalledWith('history');
  });
});
