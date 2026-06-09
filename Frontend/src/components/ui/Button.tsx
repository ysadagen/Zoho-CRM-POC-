import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { Link } from 'react-router-dom';

import { cx } from '@/lib/cx';

import { Icon, type IconName } from './Icon';

export type ButtonVariant = 'pri' | 'sec' | 'dng' | 'ghost' | 'txt';
export type ButtonSize = 'md' | 'sm';

/** Shared class composition so `<Button>` and `<ButtonLink>` stay identical. */
function btnClass(variant: ButtonVariant = 'sec', size?: ButtonSize, iconOnly = false): string {
  return cx('btn', `btn-${variant}`, size === 'sm' && 'btn-sm', iconOnly && 'btn-icon');
}

interface BaseProps {
  variant?: ButtonVariant;
  size?: ButtonSize;
  icon?: IconName;
  iconOnly?: boolean;
}

export interface ButtonProps extends BaseProps, ButtonHTMLAttributes<HTMLButtonElement> {
  loading?: boolean;
}

export function Button({
  variant = 'sec',
  size,
  icon,
  iconOnly = false,
  loading = false,
  disabled,
  className,
  children,
  type = 'button',
  ...rest
}: ButtonProps): JSX.Element {
  return (
    <button
      type={type}
      className={cx(btnClass(variant, size, iconOnly), className)}
      disabled={disabled ?? loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {icon && <Icon name={icon} />}
      {children}
    </button>
  );
}

export interface ButtonLinkProps extends BaseProps {
  to: string;
  className?: string;
  children?: ReactNode;
}

/** A router `<Link>` styled as a button — used for navigation actions. */
export function ButtonLink({
  to,
  variant = 'sec',
  size,
  icon,
  iconOnly = false,
  className,
  children,
}: ButtonLinkProps): JSX.Element {
  return (
    <Link to={to} className={cx(btnClass(variant, size, iconOnly), className)}>
      {icon && <Icon name={icon} />}
      {children}
    </Link>
  );
}
