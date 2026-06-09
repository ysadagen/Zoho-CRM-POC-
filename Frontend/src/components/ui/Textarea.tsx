import { forwardRef, type TextareaHTMLAttributes } from 'react';

import { cx } from '@/lib/cx';

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  /** Adds the error ring; pair with `aria-invalid`. */
  invalid?: boolean;
}

/** forwardRef so React Hook Form's `register()` can attach its ref. */
export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { invalid, className, ...rest },
  ref,
) {
  return (
    <textarea
      ref={ref}
      className={cx('textarea', invalid && 'error', className)}
      aria-invalid={invalid || undefined}
      {...rest}
    />
  );
});
