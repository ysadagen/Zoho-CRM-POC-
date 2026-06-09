import type { CSSProperties } from 'react';

import { cx } from '@/lib/cx';

export type BarTone = 'default' | 'success' | 'danger';

export interface ProgressBarProps {
  value: number;
  max?: number;
  tone?: BarTone;
  /**
   * Override the fill colour with a design token, e.g. `var(--accent)` for an
   * "approaching minimum" bar. The width is always data-driven.
   */
  fillVar?: string;
  className?: string;
}

export function ProgressBar({
  value,
  max = 100,
  tone = 'default',
  fillVar,
  className,
}: ProgressBarProps): JSX.Element {
  const pct = max > 0 ? Math.max(0, Math.min(100, (value / max) * 100)) : 0;
  const fillStyle: CSSProperties = { width: `${pct}%` };
  if (fillVar) fillStyle.background = fillVar;

  return (
    <div className={cx('bar', tone !== 'default' && tone, className)}>
      <div className="fill" style={fillStyle} />
    </div>
  );
}
