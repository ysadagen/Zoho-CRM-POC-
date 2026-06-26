import { useQuery } from '@tanstack/react-query';

import { useDebounce } from '@/hooks/useDebounce';

import { runSearch } from '../api/search.api';
import type { SearchGroup } from '../search.types';

/** Minimum trimmed length before we hit the network. */
export const MIN_QUERY_LENGTH = 2;

const DEBOUNCE_MS = 250;

export interface GlobalSearchState {
  /** Source groups in display order (empty until a search has resolved). */
  groups: SearchGroup[];
  /** The debounced, trimmed query the groups correspond to. */
  query: string;
  /** True once the query is long enough to search. */
  active: boolean;
  /** True while the first results for the current query are loading. */
  isLoading: boolean;
  /** True if the search query itself rejected (not a single-source failure). */
  isError: boolean;
}

/**
 * Debounced, cached global search. Stays idle (no fetch) until the trimmed
 * query reaches {@link MIN_QUERY_LENGTH}. Single-source failures are folded
 * into the groups (`group.failed`) by the service, so `isError` here only
 * trips if the whole fan-out rejects.
 */
export function useGlobalSearch(rawQuery: string): GlobalSearchState {
  const query = useDebounce(rawQuery.trim(), DEBOUNCE_MS);
  const active = query.length >= MIN_QUERY_LENGTH;

  const result = useQuery({
    queryKey: ['global-search', query],
    queryFn: () => runSearch(query),
    enabled: active,
    staleTime: 30_000,
  });

  return {
    groups: result.data ?? [],
    query,
    active,
    isLoading: active && result.isLoading,
    isError: result.isError,
  };
}
