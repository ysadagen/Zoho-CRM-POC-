import { routes } from '@/app/routes';
import { PageHeader } from '@/components/layout/PageHeader';
import { ButtonLink } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';

export function NotFoundPage(): JSX.Element {
  return (
    <>
      <PageHeader title="Page not found" />
      <Card>
        <div className="empty">
          <div className="ttl">404 — nothing here</div>
          <div className="sub">
            The page you&rsquo;re looking for doesn&rsquo;t exist or has moved.
          </div>
          <ButtonLink to={routes.dashboard} variant="pri">
            Back to Dashboard
          </ButtonLink>
        </div>
      </Card>
    </>
  );
}
