import type { ReactNode } from 'react';

import { cx } from '@/lib/cx';

export interface CardProps {
  /** Apply the standard 22px content padding. */
  pad?: boolean;
  className?: string;
  children: ReactNode;
}

export function Card({ pad = false, className, children }: CardProps): JSX.Element {
  return <div className={cx('card', pad && 'card-pad', className)}>{children}</div>;
}

export interface CardHeaderProps {
  title: ReactNode;
  sub?: ReactNode;
  /** Right-aligned action (e.g. a "View all →" link). */
  action?: ReactNode;
}

export function CardHeader({ title, sub, action }: CardHeaderProps): JSX.Element {
  return (
    <div className="card-head">
      <div>
        <h3>{title}</h3>
        {sub && <div className="sub">{sub}</div>}
      </div>
      {action}
    </div>
  );
}
