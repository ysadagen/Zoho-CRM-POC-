import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { Pager } from './Pager';

describe('Pager', () => {
  it('summarises the visible range and current page', () => {
    render(<Pager total={142} limit={25} offset={25} onChange={() => {}} />);
    expect(screen.getByText('26–50 of 142')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('of 6')).toBeInTheDocument();
  });

  it('disables Previous on the first page and Next on the last', () => {
    const { rerender } = render(<Pager total={40} limit={25} offset={0} onChange={() => {}} />);
    expect(screen.getByRole('button', { name: 'Previous page' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Next page' })).toBeEnabled();

    rerender(<Pager total={40} limit={25} offset={25} onChange={() => {}} />);
    expect(screen.getByRole('button', { name: 'Next page' })).toBeDisabled();
  });

  it('advances the offset on Next', async () => {
    const onChange = vi.fn();
    render(<Pager total={100} limit={25} offset={0} onChange={onChange} />);
    await userEvent.click(screen.getByRole('button', { name: 'Next page' }));
    expect(onChange).toHaveBeenCalledWith({ limit: 25, offset: 25 });
  });

  it('resets to the first page when page size changes', async () => {
    const onChange = vi.fn();
    render(<Pager total={100} limit={25} offset={50} onChange={onChange} />);
    await userEvent.selectOptions(screen.getByLabelText('Rows per page'), '50');
    expect(onChange).toHaveBeenCalledWith({ limit: 50, offset: 0 });
  });

  it('shows 0–0 of 0 for an empty result', () => {
    render(<Pager total={0} limit={25} offset={0} onChange={() => {}} />);
    expect(screen.getByText('0–0 of 0')).toBeInTheDocument();
  });
});
