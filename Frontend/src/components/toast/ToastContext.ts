import { createContext } from 'react';

export type ToastVariant = 'success' | 'info' | 'warn' | 'danger';

export interface ToastAction {
  label: string;
  onClick: () => void;
}

export interface ToastOptions {
  /** Rendered as a mono second line — REQUIRED on danger toasts (§5.6). */
  requestId?: string;
  /** Optional inline action button (e.g. "Refresh stock"). */
  action?: ToastAction;
  /** Keep visible longer (12 s vs 4.5 s) — use for messages with an action. */
  persist?: boolean;
}

export interface Toast extends ToastOptions {
  id: string;
  variant: ToastVariant;
  message: string;
}

export interface ToastApi {
  success: (message: string, opts?: ToastOptions) => void;
  info: (message: string, opts?: ToastOptions) => void;
  warn: (message: string, opts?: ToastOptions) => void;
  danger: (message: string, opts?: ToastOptions) => void;
  dismiss: (id: string) => void;
}

export const ToastContext = createContext<ToastApi | null>(null);
