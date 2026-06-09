import { Outlet } from 'react-router-dom';

import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';
import { Footer } from './Footer';

/** The authenticated app chrome: sidebar + (topbar · page · footer). */
export function AppShell(): JSX.Element {
  return (
    <div className="app">
      <Sidebar />
      <div className="main">
        <Topbar />
        <div className="content">
          <Outlet />
        </div>
        <Footer />
      </div>
    </div>
  );
}
