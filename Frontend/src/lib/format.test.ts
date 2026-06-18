import { describe, it, expect } from 'vitest';

import {
  formatCurrency,
  formatQuantity,
  formatSignedQuantity,
  formatDate,
  formatDateTime,
  formatTime,
  formatLongDate,
  formatRelative,
} from './format';

describe('formatCurrency', () => {
  it('formats a number as INR with two decimals', () => {
    expect(formatCurrency(1234.5)).toMatch(/₹\s?1,234\.50/);
  });

  it('accepts a Decimal string from the Backend', () => {
    expect(formatCurrency('1234.5')).toMatch(/1,234\.50/);
  });

  it('returns an em dash for null / undefined / empty / NaN', () => {
    expect(formatCurrency(null)).toBe('—');
    expect(formatCurrency(undefined)).toBe('—');
    expect(formatCurrency('')).toBe('—');
    expect(formatCurrency('not-a-number')).toBe('—');
  });
});

describe('formatQuantity', () => {
  it('appends the unit when provided', () => {
    expect(formatQuantity(120, 'pcs')).toBe('120 pcs');
  });

  it('omits the unit when not provided', () => {
    expect(formatQuantity(120)).toBe('120');
  });

  it('returns an em dash for null', () => {
    expect(formatQuantity(null, 'kg')).toBe('—');
  });
});

describe('formatSignedQuantity', () => {
  it('prefixes a plus sign for positive values', () => {
    expect(formatSignedQuantity(500, 'kg')).toBe('+500 kg');
  });

  it('prefixes a Unicode minus for negative values', () => {
    expect(formatSignedQuantity(-120, 'pcs')).toBe('−120 pcs');
  });

  it('has no sign for zero', () => {
    expect(formatSignedQuantity(0)).toBe('0');
  });
});

describe('date formatters', () => {
  // Use explicit local Date components so the result is timezone-independent.
  const may28 = new Date(2026, 4, 28, 14, 32);

  it('formatDate renders "28 May 2026"', () => {
    expect(formatDate(may28)).toBe('28 May 2026');
  });

  it('formatDateTime includes the 24h time', () => {
    expect(formatDateTime(may28)).toContain('28 May 2026');
    expect(formatDateTime(may28)).toContain('14:32');
  });

  it('formatTime renders 24h time', () => {
    expect(formatTime(may28)).toBe('14:32');
  });

  it('formatLongDate renders the weekday + date', () => {
    expect(formatLongDate(may28)).toBe('Thursday, 28 May 2026');
  });

  it('returns an em dash for null / invalid dates', () => {
    expect(formatDate(null)).toBe('—');
    expect(formatDate('not-a-date')).toBe('—');
    expect(formatDateTime(undefined)).toBe('—');
    expect(formatTime('')).toBe('—');
    expect(formatLongDate(null)).toBe('—');
    expect(formatLongDate('not-a-date')).toBe('—');
  });
});

describe('formatRelative', () => {
  it('reports minutes ago for recent timestamps', () => {
    expect(formatRelative(new Date(Date.now() - 5 * 60_000))).toBe('5 min ago');
  });

  it('reports "just now" for sub-minute deltas', () => {
    expect(formatRelative(new Date(Date.now() - 5_000))).toBe('just now');
  });

  it('reports hours ago within a day', () => {
    expect(formatRelative(new Date(Date.now() - 2 * 3_600_000))).toBe('2 h ago');
  });

  it('reports days ago within a month', () => {
    expect(formatRelative(new Date(Date.now() - 3 * 86_400_000))).toBe('3 d ago');
  });

  it('falls back to an absolute date beyond 30 days', () => {
    const old = new Date(2020, 0, 15);
    expect(formatRelative(old)).toBe(formatDate(old));
  });

  it('returns an em dash for null', () => {
    expect(formatRelative(null)).toBe('—');
  });
});

