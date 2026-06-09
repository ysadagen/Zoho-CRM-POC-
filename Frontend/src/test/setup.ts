/**
 * Vitest global setup — runs once before the test files.
 *
 * - Extends `expect` with jest-dom matchers (toBeInTheDocument, etc.).
 * - Unmounts React trees after each test so renders don't leak between cases.
 */

import '@testing-library/jest-dom/vitest';
import { afterEach } from 'vitest';
import { cleanup, configure } from '@testing-library/react';

// v8 coverage instrumentation slows React renders enough that the default
// 1000 ms async-utility timeout trips on integration tests. Give findBy*/
// waitFor headroom so the coverage gate isn't flaky on slower machines/CI.
configure({ asyncUtilTimeout: 10_000 });

afterEach(() => {
  cleanup();
});
