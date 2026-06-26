import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { Icon } from '@/components/ui/Icon';

import { MIN_QUERY_LENGTH, useGlobalSearch } from '../hooks/useGlobalSearch';
import type { SearchResult } from '../search.types';

export interface SearchPaletteProps {
  /** Close the palette (Esc, backdrop click, or after navigating). */
  onClose: () => void;
}

/** The command-palette overlay. Owns the query input and keyboard navigation;
 *  data comes from {@link useGlobalSearch}. Rendered only while open. */
export function SearchPalette({ onClose }: SearchPaletteProps): JSX.Element {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [value, setValue] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);

  const { groups, query, active, isLoading, isError } = useGlobalSearch(value);
  const flat: SearchResult[] = groups.flatMap((g) => g.results);

  // Focus the input as soon as the palette mounts.
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Reset the highlight whenever the resolved query changes.
  useEffect(() => {
    setActiveIndex(0);
  }, [query]);

  function go(result: SearchResult): void {
    navigate(result.route);
    onClose();
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLDivElement>): void {
    if (event.key === 'Escape') {
      event.preventDefault();
      onClose();
      return;
    }
    if (flat.length === 0) return;
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, flat.length - 1));
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (event.key === 'Enter') {
      event.preventDefault();
      const target = flat[Math.min(activeIndex, flat.length - 1)];
      if (target) go(target);
    }
  }

  const anyFailed = groups.some((g) => g.failed);
  const showEmpty = active && !isLoading && !isError && flat.length === 0 && !anyFailed;

  let cursor = 0;

  return (
    <div className="search-overlay" onMouseDown={onClose}>
      <div
        className="search-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Search"
        onMouseDown={(e) => e.stopPropagation()}
        onKeyDown={onKeyDown}
      >
        <div className="search-input-row">
          <Icon name="search" />
          <input
            ref={inputRef}
            type="text"
            className="search-input"
            placeholder="Search customers, items, vendors…"
            aria-label="Search customers, items, and vendors"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            autoComplete="off"
            spellCheck={false}
          />
          <button type="button" className="kbd" onClick={onClose} aria-label="Close search">
            esc
          </button>
        </div>

        <div className="search-results" role="listbox" aria-label="Search results">
          {!active && (
            <p className="search-hint">
              Type at least {MIN_QUERY_LENGTH} characters to search.
            </p>
          )}
          {active && isLoading && <p className="search-hint">Searching…</p>}
          {active && isError && (
            <p className="search-hint danger">Search is unavailable right now. Try again.</p>
          )}
          {showEmpty && (
            <p className="search-hint">
              No results for “{query}”.
            </p>
          )}

          {active &&
            !isLoading &&
            !isError &&
            groups.map((group) => {
              if (!group.failed && group.results.length === 0) return null;
              return (
                <div key={group.entity} className="search-group">
                  <div className="search-group-title">
                    <Icon name={group.icon} size={13} />
                    <span>{group.title}</span>
                  </div>
                  {group.failed ? (
                    <p className="search-hint danger">Couldn’t load {group.title}.</p>
                  ) : (
                    group.results.map((result) => {
                      const index = cursor++;
                      return (
                        <button
                          key={`${result.entity}:${result.id}`}
                          type="button"
                          role="option"
                          aria-selected={index === activeIndex}
                          className={`search-result${index === activeIndex ? ' active' : ''}`}
                          onMouseEnter={() => setActiveIndex(index)}
                          onClick={() => go(result)}
                        >
                          <span className="search-result-label">{result.label}</span>
                          {result.sublabel && (
                            <span className="search-result-sub">{result.sublabel}</span>
                          )}
                        </button>
                      );
                    })
                  )}
                </div>
              );
            })}
        </div>
      </div>
    </div>
  );
}
