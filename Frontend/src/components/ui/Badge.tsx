import type { ReactNode } from 'react';

import { cx } from '@/lib/cx';

export type BadgeVariant = 'success' | 'warn' | 'danger' | 'ink' | 'info' | 'purple';

export interface BadgeProps {
  variant: BadgeVariant;
  /** Leading status dot (colour + text, never colour alone — a11y §10). */
  dot?: boolean;
  className?: string;
  children: ReactNode;
}

export function Badge({ variant, dot = false, className, children }: BadgeProps): JSX.Element {
  return (
    <span className={cx('badge', `bd-${variant}`, className)}>
      {dot && <span className="dot" />}
      {children}
    </span>
  );
}
