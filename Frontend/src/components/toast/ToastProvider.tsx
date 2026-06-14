import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';

import { ToastContext, type Toast, type ToastApi, type ToastOptions, type ToastVariant } from './ToastContext';
import { ToastHost } from './ToastHost';

const AUTO_DISMISS_MS = 4_500;
const PERSIST_DISMISS_MS = 12_000;

export function ToastProvider({ children }: { children: ReactNode }): JSX.Element {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const idRef = useRef(0);
  const timers = useRef(new Map<string, ReturnType<typeof setTimeout>>());

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
    const timer = timers.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timers.current.delete(id);
    }
  }, []);

  const push = useCallback(
    (variant: ToastVariant, message: string, opts?: ToastOptions) => {
      idRef.current += 1;
      const id = `toast-${idRef.current}`;
      setToasts((prev) => [...prev, { id, variant, message, ...opts }]);
      const ttl = opts?.persist ? PERSIST_DISMISS_MS : AUTO_DISMISS_MS;
      timers.current.set(id, setTimeout(() => dismiss(id), ttl));
    },
    [dismiss],
  );

  // Clear any pending timers if the provider unmounts.
  useEffect(() => {
    const pending = timers.current;
    return () => {
      for (const timer of pending.values()) clearTimeout(timer);
      pending.clear();
    };
  }, []);

  const api = useMemo<ToastApi>(
    () => ({
      success: (message, opts) => push('success', message, opts),
      info: (message, opts) => push('info', message, opts),
      warn: (message, opts) => push('warn', message, opts),
      danger: (message, opts) => push('danger', message, opts),
      dismiss,
    }),
    [push, dismiss],
  );

  return (
    <ToastContext.Provider value={api}>
      {children}
      <ToastHost toasts={toasts} onDismiss={dismiss} />
    </ToastContext.Provider>
  );
}
