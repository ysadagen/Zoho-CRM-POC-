/**
 * The application icon set — inline SVGs ported verbatim from the design's
 * `chrome.js` (`ADAGEN_ICONS`) plus the glyphs used on the dashboard.
 *
 * Icons inherit colour via `stroke="currentColor"` and are sized either by the
 * `size` prop or by the surrounding CSS context rule (`.nav-item svg`,
 * `.btn svg`, …). Decorative by default (`aria-hidden`); pass a `title` for a
 * meaningful standalone icon.
 */
import type { ReactNode } from 'react';

export type IconName =
  | 'home'
  | 'box'
  | 'bag'
  | 'cart'
  | 'user'
  | 'truck'
  | 'swap'
  | 'cog'
  | 'bell'
  | 'search'
  | 'help'
  | 'signout'
  | 'chevDown'
  | 'plus'
  | 'refresh'
  | 'package'
  | 'alertTriangle'
  | 'sync'
  | 'check'
  | 'clock'
  | 'eye'
  | 'eyeOff'
  | 'arrowRight'
  | 'info'
  | 'close';

interface IconDef {
  /** Stroke width, preserved from the source SVG. */
  sw: number;
  body: ReactNode;
}

const ICONS: Record<IconName, IconDef> = {
  home: { sw: 1.8, body: <path d="M3 11l9-8 9 8v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1z" /> },
  box: {
    sw: 1.8,
    body: (
      <>
        <path d="M3 7l9-4 9 4-9 4z" />
        <path d="M3 7v10l9 4 9-4V7" />
        <path d="M12 11v10" />
      </>
    ),
  },
  bag: {
    sw: 1.8,
    body: (
      <>
        <path d="M6 7h12v4l-3 9H9l-3-9z" />
        <path d="M9 7V4h6v3" />
      </>
    ),
  },
  cart: {
    sw: 1.8,
    body: (
      <>
        <path d="M4 5h3l2 12h10l2-8H8" />
        <circle cx="10" cy="20" r="1.5" />
        <circle cx="17" cy="20" r="1.5" />
      </>
    ),
  },
  user: {
    sw: 1.8,
    body: (
      <>
        <circle cx="12" cy="8" r="4" />
        <path d="M4 20a8 8 0 0 1 16 0" />
      </>
    ),
  },
  truck: {
    sw: 1.8,
    body: (
      <>
        <rect x="1" y="6" width="14" height="11" rx="1" />
        <path d="M15 10h4l3 4v3h-7" />
        <circle cx="6" cy="19" r="2" />
        <circle cx="18" cy="19" r="2" />
      </>
    ),
  },
  swap: { sw: 1.8, body: <path d="M4 8h13l-3-3M20 16H7l3 3" /> },
  cog: {
    sw: 1.8,
    body: (
      <>
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" />
      </>
    ),
  },
  bell: {
    sw: 1.8,
    body: (
      <>
        <path d="M6 9a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
        <path d="M10 21a2 2 0 0 0 4 0" />
      </>
    ),
  },
  search: {
    sw: 1.8,
    body: (
      <>
        <circle cx="11" cy="11" r="7" />
        <line x1="21" y1="21" x2="16.65" y2="16.65" />
      </>
    ),
  },
  help: {
    sw: 1.8,
    body: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M9.5 9a2.5 2.5 0 1 1 4 2c-1 0.7-1.5 1.2-1.5 2.5" />
        <circle cx="12" cy="17" r="0.5" fill="currentColor" />
      </>
    ),
  },
  signout: {
    sw: 1.8,
    body: (
      <>
        <path d="M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3" />
        <polyline points="10 17 15 12 10 7" />
        <line x1="15" y1="12" x2="3" y2="12" />
      </>
    ),
  },
  chevDown: { sw: 2, body: <polyline points="6 9 12 15 18 9" /> },
  plus: {
    sw: 2,
    body: (
      <>
        <line x1="12" y1="5" x2="12" y2="19" />
        <line x1="5" y1="12" x2="19" y2="12" />
      </>
    ),
  },
  refresh: {
    sw: 2,
    body: (
      <>
        <path d="M21 12a9 9 0 1 1-3-6.7L21 8" />
        <polyline points="21 3 21 8 16 8" />
      </>
    ),
  },
  package: {
    sw: 2,
    body: (
      <>
        <path d="M3 7l9-4 9 4-9 4z" />
        <path d="M3 7v10l9 4 9-4V7" />
      </>
    ),
  },
  alertTriangle: {
    sw: 2,
    body: (
      <>
        <path d="M10.3 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
        <line x1="12" y1="9" x2="12" y2="13" />
      </>
    ),
  },
  sync: {
    sw: 2,
    body: (
      <>
        <path d="M20 7a8 8 0 0 0-14-2M4 17a8 8 0 0 0 14 2" />
        <path d="M20 3v4h-4M4 21v-4h4" />
      </>
    ),
  },
  check: { sw: 3, body: <polyline points="20 6 9 17 4 12" /> },
  clock: {
    sw: 2,
    body: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 2" />
      </>
    ),
  },
  eye: {
    sw: 2,
    body: (
      <>
        <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7z" />
        <circle cx="12" cy="12" r="3" />
      </>
    ),
  },
  eyeOff: {
    sw: 2,
    body: (
      <>
        <path d="M9.9 4.24A9.12 9.12 0 0 1 12 5c7 0 10 7 10 7a13.2 13.2 0 0 1-1.67 2.68" />
        <path d="M6.61 6.61A13.5 13.5 0 0 0 2 12s3 7 10 7a9.7 9.7 0 0 0 5.39-1.61" />
        <line x1="2" y1="2" x2="22" y2="22" />
      </>
    ),
  },
  arrowRight: {
    sw: 2,
    body: (
      <>
        <line x1="5" y1="12" x2="19" y2="12" />
        <polyline points="12 5 19 12 12 19" />
      </>
    ),
  },
  info: {
    sw: 2,
    body: (
      <>
        <circle cx="12" cy="12" r="9" />
        <line x1="12" y1="11" x2="12" y2="16" />
        <line x1="12" y1="8" x2="12.01" y2="8" />
      </>
    ),
  },
  close: {
    sw: 2.2,
    body: (
      <>
        <line x1="18" y1="6" x2="6" y2="18" />
        <line x1="6" y1="6" x2="18" y2="18" />
      </>
    ),
  },
};

export interface IconProps {
  name: IconName;
  /** Pixels. Omit to let the surrounding CSS context size the icon. */
  size?: number;
  className?: string;
  /** A label makes the icon meaningful (non-decorative) to assistive tech. */
  title?: string;
}

export function Icon({ name, size, className, title }: IconProps): JSX.Element {
  const def = ICONS[name];
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={def.sw}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      role={title ? 'img' : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
      focusable={false}
    >
      {def.body}
    </svg>
  );
}
