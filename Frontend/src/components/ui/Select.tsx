import { forwardRef, type SelectHTMLAttributes } from 'react';

import { cx } from '@/lib/cx';

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  /** Adds the error ring; pair with `aria-invalid`. */
  invalid?: boolean;
}

/** forwardRef so React Hook Form's `register()` can attach its ref. */
export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { invalid, className, children, ...rest },
  ref,
) {
  return (
    <select
      ref={ref}
      className={cx('select', invalid && 'error', className)}
      aria-invalid={invalid || undefined}
      {...rest}
    >
      {children}
    </select>
  );
});
