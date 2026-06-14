import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'node:path';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    // Fail loudly if 5173 is taken instead of silently moving to 5174+ — a
    // drifting origin breaks the Backend's CORS allow-list (which is pinned to
    // a fixed port). Free the port rather than letting the dev server wander.
    strictPort: true,
    open: false,
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    target: 'es2022',
  },
  test: {
    environment: 'jsdom',
    globals: false,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    restoreMocks: true,
    // Coverage instrumentation is slow on some machines; keep the per-test
    // ceiling well above the 10s async-utility timeout set in setup.ts.
    testTimeout: 30_000,
    hookTimeout: 30_000,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/**/*.test.{ts,tsx}',
        'src/test/**',
        'src/**/*.d.ts',
        'src/types/**',
        'src/main.tsx',
        'src/lib/api/types.ts', // type-only re-exports — no runtime code
      ],
      thresholds: {
        lines: 80,
        functions: 80,
        statements: 80,
        branches: 70,
        'src/lib/**': { lines: 95, functions: 95, statements: 95, branches: 80 },
      },
    },
  },
});
