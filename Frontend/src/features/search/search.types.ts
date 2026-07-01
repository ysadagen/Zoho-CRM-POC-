import type { IconName } from '@/components/ui/Icon';

/** The entity kinds the global palette can search. */
export type SearchEntity = 'customer' | 'item' | 'vendor' | 'lead';

/** One flattened, navigable hit. */
export interface SearchResult {
  entity: SearchEntity;
  id: string;
  label: string;
  sublabel: string | null;
  /** Route to navigate to when this result is chosen. */
  route: string;
}

/** Results for one source, in display order. `failed` is true when that
 *  source's request errored — the palette shows the others regardless. */
export interface SearchGroup {
  entity: SearchEntity;
  title: string;
  icon: IconName;
  results: SearchResult[];
  failed: boolean;
}
