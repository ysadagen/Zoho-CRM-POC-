import type { ReactNode } from 'react';

import { cx } from '@/lib/cx';

export type StockChipVariant = 'ok' | 'short' | 'warn';

/** Live stock indicator for SO create lines (DESIGN_SYSTEM §6.13, §5 non-negotiable). */
export function StockChip({
  variant,
  children,
}: {
  variant: StockChipVariant;
  children: ReactNode;
}): JSX.Element {
  return <span className={cx('stock-chip', variant)}>{children}</span>;
}
