/**
 * Display formatters.
 *
 * All Backend monetary/quantity fields arrive as strings (Decimal precision).
 * These helpers are the single boundary that turns them into UI strings.
 */

const INR_NF = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 2,
});

const QTY_NF = new Intl.NumberFormat('en-IN', {
  maximumFractionDigits: 3,
});

const INT_NF = new Intl.NumberFormat('en-IN', {
  maximumFractionDigits: 0,
});

const DATE_FMT = new Intl.DateTimeFormat('en-GB', {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
});

const DATETIME_FMT = new Intl.DateTimeFormat('en-GB', {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
});

const TIME_FMT = new Intl.DateTimeFormat('en-GB', {
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
});

const WEEKDAY_FMT = new Intl.DateTimeFormat('en-GB', { weekday: 'long' });

function toFiniteNumber(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined || value === '') return null;
  const n = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(n) ? n : null;
}

export function formatCurrency(value: string | number | null | undefined): string {
  const n = toFiniteNumber(value);
  if (n === null) return '—';
  return INR_NF.format(n);
}

export function formatQuantity(
  value: string | number | null | undefined,
  unit?: string | null,
): string {
  const n = toFiniteNumber(value);
  if (n === null) return '—';
  const num = QTY_NF.format(n);
  return unit ? `${num} ${unit}` : num;
}

export function formatSignedQuantity(
  value: string | number | null | undefined,
  unit?: string | null,
): string {
  const n = toFiniteNumber(value);
  if (n === null) return '—';
  const sign = n > 0 ? '+' : n < 0 ? '−' : '';
  const num = QTY_NF.format(Math.abs(n));
  return unit ? `${sign}${num} ${unit}` : `${sign}${num}`;
}

export function formatInteger(value: string | number | null | undefined): string {
  const n = toFiniteNumber(value);
  if (n === null) return '—';
  return INT_NF.format(n);
}

export function formatDate(value: string | Date | null | undefined): string {
  if (!value) return '—';
  const d = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(d.getTime())) return '—';
  return DATE_FMT.format(d);
}

export function formatDateTime(value: string | Date | null | undefined): string {
  if (!value) return '—';
  const d = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(d.getTime())) return '—';
  return DATETIME_FMT.format(d);
}

export function formatTime(value: string | Date | null | undefined): string {
  if (!value) return '—';
  const d = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(d.getTime())) return '—';
  return TIME_FMT.format(d);
}

/**
 * Relative humanizer for "2 hours ago", "just now" — used in audit ledger.
 */
export function formatRelative(value: string | Date | null | undefined): string {
  if (!value) return '—';
  const d = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(d.getTime())) return '—';
  const diff = Date.now() - d.getTime();
  if (diff < 60_000) return 'just now';
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} min ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)} h ago`;
  const days = Math.floor(diff / 86_400_000);
  if (days < 30) return `${days} d ago`;
  return formatDate(d);
}

/**
 * Long, human header date — e.g. "Thursday, 28 May 2026" (dashboard greeting).
 */
export function formatLongDate(value: string | Date | null | undefined): string {
  if (!value) return '—';
  const d = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(d.getTime())) return '—';
  return `${WEEKDAY_FMT.format(d)}, ${DATE_FMT.format(d)}`;
}

/**
 * Server expects `YYYY-MM-DD` for date-only fields (vendor terms, order dates).
 */
export function toIsoDate(value: Date): string {
  const yyyy = value.getFullYear();
  const mm = String(value.getMonth() + 1).padStart(2, '0');
  const dd = String(value.getDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
}
