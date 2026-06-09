export interface PagerProps {
  total: number;
  limit: number;
  offset: number;
  onChange: (next: { limit: number; offset: number }) => void;
  pageSizes?: number[];
}

const DEFAULT_SIZES = [25, 50, 100];

/**
 * Server-pagination footer: page-size selector + a "from–to of total" summary +
 * prev/next controls. Emits the next `{ limit, offset }` for the caller to push
 * to the query (changing page size resets to the first page).
 */
export function Pager({
  total,
  limit,
  offset,
  onChange,
  pageSizes = DEFAULT_SIZES,
}: PagerProps): JSX.Element {
  const totalPages = Math.max(1, Math.ceil(total / limit));
  const currentPage = Math.floor(offset / limit) + 1;
  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + limit, total);

  const goTo = (page: number): void => {
    const clamped = Math.min(Math.max(1, page), totalPages);
    onChange({ limit, offset: (clamped - 1) * limit });
  };

  return (
    <div className="tbl-foot">
      <div className="flex items-center gap-12">
        <label className="flex items-center gap-8 fs-12 text-muted">
          Rows
          {/* Inline sizing only (width/min-height) — consistent with the
              data-driven inline sizing ProgressBar/Skeleton use. */}
          <select
            className="select"
            style={{ width: 'auto', minHeight: 'auto' }}
            value={limit}
            onChange={(e) => onChange({ limit: Number(e.target.value), offset: 0 })}
            aria-label="Rows per page"
          >
            {pageSizes.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </label>
        <span className="fs-12 text-muted">
          {from}–{to} of {total}
        </span>
      </div>
      <div className="pager">
        <button
          type="button"
          className="arrow"
          aria-label="Previous page"
          disabled={currentPage <= 1}
          onClick={() => goTo(currentPage - 1)}
        >
          ‹
        </button>
        <span className="pg active" aria-current="page">
          {currentPage}
        </span>
        <span className="dots">of {totalPages}</span>
        <button
          type="button"
          className="arrow"
          aria-label="Next page"
          disabled={currentPage >= totalPages}
          onClick={() => goTo(currentPage + 1)}
        >
          ›
        </button>
      </div>
    </div>
  );
}
