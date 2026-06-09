import type { ReactNode } from 'react';

export interface FieldProps {
  label: string;
  /** Must match the control's `id` so the label is clickable + a11y-linked. */
  htmlFor: string;
  required?: boolean;
  hint?: string;
  error?: string;
  children: ReactNode;
}

/** Label + control + hint/error wrapper. The error replaces the hint. */
export function Field({ label, htmlFor, required, hint, error, children }: FieldProps): JSX.Element {
  return (
    <div className="field">
      {/* The required `*` is a CSS pseudo-element so it stays out of the
          label's accessible name (and out of label-text test queries). */}
      <label htmlFor={htmlFor} className={required ? 'is-required' : undefined}>
        {label}
      </label>
      {children}
      {error ? (
        <div className="err" role="alert">
          {error}
        </div>
      ) : (
        hint && <div className="hint">{hint}</div>
      )}
    </div>
  );
}
