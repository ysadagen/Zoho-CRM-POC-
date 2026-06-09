import { Link, NavLink } from 'react-router-dom';

import { routes } from '@/app/routes';
import { env } from '@/config/env';
import { Icon } from '@/components/ui/Icon';
import { cx } from '@/lib/cx';

import { NAV_ITEMS } from './navItems';

export function Sidebar(): JSX.Element {
  return (
    <aside className="sidebar">
      <Link className="sidebar-brand" to={routes.dashboard}>
        <div className="l1">ADAGEN</div>
        <div className="l2">INVENTORY MANAGER</div>
        <svg
          className="ul"
          viewBox="0 0 110 6"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          strokeLinecap="round"
          aria-hidden="true"
        >
          <path d="M2 3.5 C 24 1, 56 5, 84 2.5 S 100 5, 108 3" />
        </svg>
      </Link>

      <nav className="sidebar-nav">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) => cx('nav-item', isActive && 'active')}
          >
            <Icon name={item.icon} />
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-foot-min">
        <span>v0.1.0 · POC</span>
        <span className="env-chip">{env.appEnv.toUpperCase()}</span>
      </div>
    </aside>
  );
}
