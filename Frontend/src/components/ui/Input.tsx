import { forwardRef, type InputHTMLAttributes } from 'react';

import { cx } from '@/lib/cx';

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  /** Adds the error ring; pair with `aria-invalid` for assistive tech. */
  invalid?: boolean;
}

/** forwardRef so React Hook Form's `register()` can attach its ref. */
export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { invalid, className, ...rest },
  ref,
) {
  return (
    <input
      ref={ref}
      className={cx('input', invalid && 'error', className)}
      aria-invalid={invalid || undefined}
      {...rest}
    />
  );
});
