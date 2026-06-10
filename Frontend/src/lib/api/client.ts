/**
 * The single shared axios instance for the entire app.
 *
 * Responsibilities:
 *  - Attach the auth bearer (when present) and a client `X-Request-ID`.
 *  - Normalise every error to `ApiError` (no `AxiosError` escapes this file).
 *  - On auth-failure codes, clear the session and steer the browser to login.
 *
 * NOTE: callers receive the JSON body directly (response interceptor unwraps).
 * Use the typed helper functions exported below.
 */

import axios, { type AxiosInstance, type AxiosRequestConfig, type AxiosError } from 'axios';

import { env } from '@/config/env';
import { logger } from '@/lib/logger';

import { ApiError, fromAxiosError } from './errors';
import { REQUEST_ID_HEADER, newRequestId } from './request-id';

const AUTH_HEADER = 'Authorization';

/**
 * The browser-side place where the auth bearer lives. Kept here as a thin
 * indirection so we don't import the auth module from inside `lib/` (would
 * create a layering cycle). The auth module installs its getter at startup.
 */
let tokenGetter: () => string | null = () => null;

/**
 * Called once at app boot, before any API requests. Lets the auth context
 * decide where tokens live without `lib/api/` knowing about React.
 */
export function configureAuthTokenSource(getter: () => string | null): void {
  tokenGetter = getter;
}

/**
 * Called by the response interceptor when an auth failure is seen. The auth
 * module installs the redirect; `lib/api/` never imports the router.
 */
let authFailureHandler: (error: ApiError) => void = () => {};

export function configureAuthFailureHandler(handler: (error: ApiError) => void): void {
  authFailureHandler = handler;
}

/**
 * Endpoints that are part of the *login* flow itself — 401s here are normal
 * UX and must NOT trigger the global redirect.
 */
const AUTH_FLOW_PATHS = new Set(['/api/v1/auth/login', '/api/v1/auth/register']);

function isAuthFlowRequest(config: AxiosRequestConfig | undefined): boolean {
  const url = config?.url ?? '';
  return AUTH_FLOW_PATHS.has(url);
}

export const httpClient: AxiosInstance = axios.create({
  baseURL: env.apiBaseUrl,
  timeout: 30_000,
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
});

httpClient.interceptors.request.use((config) => {
  const requestId = newRequestId();
  config.headers.set(REQUEST_ID_HEADER, requestId);

  const token = tokenGetter();
  if (token) {
    config.headers.set(AUTH_HEADER, `Bearer ${token}`);
  }

  // Stash the client-generated ID so the response interceptor can fall back
  // to it if the server didn't return its own (e.g. network error before
  // the request reached the server).
  (config as AxiosRequestConfig & { metadata?: { requestId: string } }).metadata = {
    requestId,
  };

  if (env.isDev) {
    logger.debug('http.request', {
      method: config.method?.toUpperCase(),
      url: config.url,
      requestId,
    });
  }

  return config;
});

httpClient.interceptors.response.use(
  (response) => {
    if (env.isDev) {
      const requestId =
        (response.config as AxiosRequestConfig & { metadata?: { requestId?: string } }).metadata
          ?.requestId ?? '—';
      logger.debug('http.response', {
        status: response.status,
        url: response.config.url,
        requestId,
      });
    }
    return response;
  },
  (error: AxiosError) => {
    const fallbackRequestId =
      (error.config as AxiosRequestConfig & { metadata?: { requestId?: string } })?.metadata
        ?.requestId ?? 'unknown';
    const apiError = fromAxiosError(error, fallbackRequestId);

    logger.error('http.error', {
      code: apiError.code,
      httpStatus: apiError.httpStatus,
      requestId: apiError.requestId,
      url: error.config?.url,
    });

    if (apiError.isAuthFailure() && !isAuthFlowRequest(error.config)) {
      authFailureHandler(apiError);
    }

    return Promise.reject(apiError);
  },
);

// =============================================================
//  Typed helpers used by feature *.api.ts files.
//  These narrow the axios surface so callers can't shoot themselves
//  in the foot (e.g. forgetting <T> and getting any).
// =============================================================

export async function apiGet<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  const res = await httpClient.get<T>(url, config);
  return res.data;
}

export async function apiPost<T, B = unknown>(
  url: string,
  body?: B,
  config?: AxiosRequestConfig,
): Promise<T> {
  const res = await httpClient.post<T>(url, body, config);
  return res.data;
}

export async function apiPatch<T, B = unknown>(
  url: string,
  body?: B,
  config?: AxiosRequestConfig,
): Promise<T> {
  const res = await httpClient.patch<T>(url, body, config);
  return res.data;
}

export async function apiDelete<T = void>(
  url: string,
  config?: AxiosRequestConfig,
): Promise<T> {
  const res = await httpClient.delete<T>(url, config);
  return res.data;
}
