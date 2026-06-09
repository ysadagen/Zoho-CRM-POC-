import { forwardRef, useState } from 'react';

import { Icon } from '@/components/ui/Icon';
import { Input, type InputProps } from '@/components/ui/Input';

/** Password input with a show/hide toggle (UI_SPECIFICATION.md §6.1). */
export const PasswordInput = forwardRef<HTMLInputElement, InputProps>(function PasswordInput(
  props,
  ref,
) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="pw-field">
      <Input ref={ref} type={visible ? 'text' : 'password'} {...props} />
      <button
        type="button"
        className="pw-toggle"
        onClick={() => setVisible((v) => !v)}
        aria-label={visible ? 'Hide password' : 'Show password'}
        aria-pressed={visible}
      >
        <Icon name={visible ? 'eyeOff' : 'eye'} size={16} />
      </button>
    </div>
  );
});
