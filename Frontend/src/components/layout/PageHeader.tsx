import type { ReactNode } from 'react';

export interface PageHeaderProps {
  title: ReactNode;
  sub?: ReactNode;
  /** Right-aligned primary/secondary actions for the page. */
  actions?: ReactNode;
}

export function PageHeader({ title, sub, actions }: PageHeaderProps): JSX.Element {
  return (
    <div className="page-head">
      <div>
        <h1>{title}</h1>
        {sub && <div className="sub">{sub}</div>}
      </div>
      {actions && <div className="actions">{actions}</div>}
    </div>
  );
}
