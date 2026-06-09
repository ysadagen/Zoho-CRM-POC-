import { Outlet } from 'react-router-dom';

import '@/styles/login.css';

/** Two-pane auth layout: brand/pitch panel + the form (via <Outlet/>). */
export function AuthShell(): JSX.Element {
  return (
    <div className="auth-wrap">
      <div className="auth-side">
        <div className="auth-brand">
          <div className="l1">ADAGEN</div>
          <div className="l2">INVENTORY MANAGER</div>
          <svg
            className="ul"
            viewBox="0 0 180 7"
            fill="none"
            stroke="currentColor"
            strokeWidth={2.4}
            strokeLinecap="round"
            aria-hidden="true"
          >
            <path d="M2 4 C 30 1, 70 6, 110 3 S 160 5.5, 178 3" />
          </svg>
        </div>

        <div className="auth-pitch">
          <h2>Every bottle, every batch, every order — accounted for.</h2>
          <p>
            Manage raw materials, finished products, vendors and customers in one operational
            hub. Synced with Zoho CRM so your team stays on the same page from shop floor to
            sales call.
          </p>
          <div className="stats">
            <div className="stat">
              <div className="v">₹ 24.6L</div>
              <div className="l">Stock value tracked</div>
            </div>
            <div className="stat">
              <div className="v">98.4%</div>
              <div className="l">CRM sync uptime</div>
            </div>
            <div className="stat">
              <div className="v">3 sec</div>
              <div className="l">Avg. order entry</div>
            </div>
          </div>
        </div>

        <div className="auth-foot">
          <span>© 2026 Adagen Manufacturing Pvt. Ltd.</span>
          <span>Privacy · Terms · Support</span>
        </div>
      </div>

      <div className="auth-form-wrap">
        <Outlet />
      </div>
    </div>
  );
}
