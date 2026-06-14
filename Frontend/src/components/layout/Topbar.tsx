import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';

import { routes } from '@/app/routes';
import { useAuth } from '@/auth/useAuth';
import { Icon } from '@/components/ui/Icon';

import { navItemForPath } from './navItems';

function initialsOf(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0]!.slice(0, 2).toUpperCase();
  return (parts[0]![0]! + parts[parts.length - 1]![0]!).toUpperCase();
}

export function Topbar(): JSX.Element {
  const { pathname } = useLocation();
  const { user, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);

  const crumb = navItemForPath(pathname)?.label ?? 'Dashboard';
  const name = user?.full_name ?? 'User';
  const role = user?.is_admin ? 'Administrator' : 'Operations';

  return (
    <header className="topbar">
      <div className="crumbs">
        <Link to={routes.dashboard} className="crumb-root">
          Adagen
        </Link>
        <span className="sep">/</span>
        <span className="now">{crumb}</span>
      </div>

      <div className="search-wrap">
        <div className="search disabled" title="Phase 2 — coming soon">
          <Icon name="search" />
          <span className="placeholder">Search (coming soon)</span>
          <span className="kbd">⌘K</span>
        </div>
      </div>

      <div className="topbar-actions">
        <button className="iconbtn" type="button" title="Help" aria-label="Help">
          <Icon name="help" />
        </button>
        <button
          className="iconbtn"
          type="button"
          title="Notifications (Phase 2)"
          aria-label="Notifications"
        >
          <Icon name="bell" />
          <span className="dot" />
        </button>

        <div className="menu-anchor">
          <button
            type="button"
            className="user-menu"
            onClick={() => setMenuOpen((open) => !open)}
            aria-haspopup="menu"
            aria-expanded={menuOpen}
            aria-label="Account menu"
          >
            <span className="avatar-sm">{initialsOf(name)}</span>
            <div className="who">
              <span className="name">{name}</span>
              <span className="role">{role}</span>
            </div>
            <Icon name="chevDown" />
          </button>

          {menuOpen && (
            <>
              <div className="menu-backdrop" onClick={() => setMenuOpen(false)} />
              <div className="menu-pop" role="menu">
                <Link
                  className="menu-item"
                  role="menuitem"
                  to={routes.settings}
                  onClick={() => setMenuOpen(false)}
                >
                  <Icon name="cog" size={14} />
                  Settings
                </Link>
                <div className="menu-sep" />
                <button
                  type="button"
                  className="menu-item danger"
                  role="menuitem"
                  onClick={() => {
                    setMenuOpen(false);
                    logout();
                  }}
                >
                  <Icon name="signout" size={14} />
                  Log out
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
