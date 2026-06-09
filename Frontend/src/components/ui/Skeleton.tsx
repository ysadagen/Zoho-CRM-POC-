import type { CSSProperties } from 'react';

import { cx } from '@/lib/cx';

export interface SkeletonProps {
  /** CSS width, e.g. "60%" or 120. */
  width?: string | number;
  /** CSS height, e.g. 14. */
  height?: string | number;
  className?: string;
}

/**
 * Shimmer placeholder for loading states (DESIGN_SYSTEM §6.11). Width/height
 * are data-driven inline sizing — the same exemption ProgressBar uses for its
 * fill; colour/radius/animation all live in the `.skeleton` class.
 */
export function Skeleton({ width, height, className }: SkeletonProps): JSX.Element {
  const style: CSSProperties = {};
  if (width !== undefined) style.width = width;
  if (height !== undefined) style.height = height;
  return <div className={cx('skeleton', className)} style={style} aria-hidden="true" />;
}
