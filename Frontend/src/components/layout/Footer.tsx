import { env } from '@/config/env';

export function Footer(): JSX.Element {
  return (
    <footer className="app-footer">
      <span>Adagen Inventory Manager · v0.1.0</span>
      <span className="env-chip small">{env.appEnv.toUpperCase()}</span>
      <span className="spacer" />
      <span>© 2026 Adagen Manufacturing Pvt. Ltd.</span>
    </footer>
  );
}
