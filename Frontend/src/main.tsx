/**
 * Bootstrap: load the design-system styles and mount <App/>. The provider
 * tree (ErrorBoundary, QueryClient, Router, Auth, Toast) lives in `@/app/App`.
 */

import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { App } from '@/app/App';
import './styles/fonts.css';
import './styles/globals.css';

const rootEl = document.getElementById('root');
if (!rootEl) {
  throw new Error('#root element missing in index.html');
}

createRoot(rootEl).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
