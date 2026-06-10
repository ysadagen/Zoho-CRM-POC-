/**
 * Structured browser logger.
 *
 * Single sink for every log line. Feature code MUST go through this — no
 * direct `console.*` calls. Centralising the surface lets us add redaction,
 * remote shipping, or environment-conditional thresholds without touching
 * call sites.
 */

import { env } from '@/config/env';

type Level = 'debug' | 'info' | 'warn' | 'error';

const LEVEL_ORDER: Record<Level, number> = { debug: 10, info: 20, warn: 30, error: 40 };

const THRESHOLD: Level = env.isDev ? 'debug' : 'info';

/**
 * Field keys that must never appear in a log line. Anything matching these
 * is redacted before emit. Defence-in-depth — callers should already avoid
 * passing them.
 */
const REDACTED_KEYS = new Set([
  'password',
  'new_password',
  'current_password',
  'confirm_password',
  'authorization',
  'access_token',
  'refresh_token',
  'token',
]);

function redact(fields: Record<string, unknown> | undefined): Record<string, unknown> {
  if (!fields) return {};
  const out: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(fields)) {
    if (REDACTED_KEYS.has(key.toLowerCase())) {
      out[key] = '[redacted]';
    } else {
      out[key] = value;
    }
  }
  return out;
}

function shouldLog(level: Level): boolean {
  return LEVEL_ORDER[level] >= LEVEL_ORDER[THRESHOLD];
}

function emit(level: Level, scope: string, fields: Record<string, unknown> | undefined): void {
  if (!shouldLog(level)) return;
  const payload = { scope, ...redact(fields) };
  switch (level) {
    case 'debug':
      console.debug(`[${scope}]`, payload);
      break;
    case 'info':
      console.info(`[${scope}]`, payload);
      break;
    case 'warn':
      console.warn(`[${scope}]`, payload);
      break;
    case 'error':
      console.error(`[${scope}]`, payload);
      break;
  }
}

export const logger = {
  debug(scope: string, fields?: Record<string, unknown>) {
    emit('debug', scope, fields);
  },
  info(scope: string, fields?: Record<string, unknown>) {
    emit('info', scope, fields);
  },
  warn(scope: string, fields?: Record<string, unknown>) {
    emit('warn', scope, fields);
  },
  error(scope: string, fields?: Record<string, unknown>) {
    emit('error', scope, fields);
  },
};
