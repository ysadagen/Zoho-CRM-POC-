import type { ReactNode } from 'react';

import { Icon, type IconName } from './Icon';

export interface EmptyStateProps {
  icon?: IconName;
  title: string;
  sub?: string;
  /** Optional CTA (e.g. a "+ Add Item" button). */
  action?: ReactNode;
}

/** The standard empty state for list views and tabs (DESIGN_SYSTEM §6.11). */
export function EmptyState({ icon, title, sub, action }: EmptyStateProps): JSX.Element {
  return (
    <div className="empty">
      {icon && (
        <div className="ill">
          <Icon name={icon} size={28} />
        </div>
      )}
      <div className="ttl">{title}</div>
      {sub && <div className="sub">{sub}</div>}
      {action}
    </div>
  );
}
