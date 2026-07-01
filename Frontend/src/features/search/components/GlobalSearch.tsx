import { useCallback, useEffect, useState } from 'react';

import { Icon } from '@/components/ui/Icon';

import { SearchPalette } from './SearchPalette';

/**
 * The Topbar search affordance plus the command palette it opens. Owns the
 * open/closed state and the global ⌘K / Ctrl+K shortcut. Replaces the old
 * "coming soon" placeholder.
 */
export function GlobalSearch(): JSX.Element {
  const [open, setOpen] = useState(false);

  const close = useCallback(() => setOpen(false), []);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent): void {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setOpen(true);
        return;
      }
      if (event.key === 'Escape' && open) {
        event.preventDefault();
        close();
      }
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open, close]);

  return (
    <div className="search-wrap">
      <button
        type="button"
        className="search"
        onClick={() => setOpen(true)}
        aria-label="Search (Ctrl or Cmd K)"
      >
        <Icon name="search" />
        <span className="placeholder">Search</span>
        <span className="kbd">⌘K</span>
      </button>
      {open && <SearchPalette onClose={close} />}
    </div>
  );
}
