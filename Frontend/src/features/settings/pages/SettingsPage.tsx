import { useState } from 'react';

import { useAuth } from '@/auth/useAuth';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader } from '@/components/ui/Card';

import { EditNameModal } from '../components/EditNameModal';
import '../settings.css';

export function SettingsPage(): JSX.Element | null {
  const { user } = useAuth();
  const [editOpen, setEditOpen] = useState(false);

  // ProtectedRoute guarantees a user; guard keeps the type narrow.
  if (!user) return null;

  const role = user.is_admin ? 'Administrator' : 'Operations';

  return (
    <>
      <PageHeader title="Settings" sub="Your profile and account" />

      <Card>
        <CardHeader
          title="Profile"
          sub="Your account details"
          action={
            <Button variant="sec" size="sm" onClick={() => setEditOpen(true)}>
              Edit name
            </Button>
          }
        />
        <div className="settings-body">
          <div className="settings-grid">
            <div className="label-pair">
              <span className="l">Name</span>
              <span className="v">{user.full_name}</span>
            </div>
            <div className="label-pair">
              <span className="l">Email</span>
              <span className="v">{user.email}</span>
            </div>
            <div className="label-pair">
              <span className="l">Role</span>
              <span className="v">{role}</span>
            </div>
          </div>
        </div>
      </Card>

      <Card className="mt-16">
        <CardHeader
          title="Password"
          sub="Change your account password"
          action={
            // No password-change endpoint in the Backend yet — honest placeholder.
            <button className="btn btn-sec btn-sm" type="button" disabled title="Coming soon">
              Change password
            </button>
          }
        />
        <div className="settings-body text-muted fs-12">
          Password changes aren&apos;t available yet.
        </div>
      </Card>

      {editOpen && <EditNameModal user={user} onClose={() => setEditOpen(false)} />}
    </>
  );
}
