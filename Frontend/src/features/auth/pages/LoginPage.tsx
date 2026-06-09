import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { z } from 'zod';

import { routes } from '@/app/routes';
import { useAuth } from '@/auth/useAuth';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { ApiError } from '@/lib/api/errors';

import { AuthAlert } from '../components/AuthAlert';
import { PasswordInput } from '../components/PasswordInput';
import '../auth.css';

const loginSchema = z.object({
  email: z.string().min(1, 'Email is required').email('Enter a valid email address'),
  password: z.string().min(1, 'Password is required'),
});

type LoginValues = z.infer<typeof loginSchema>;

interface FormAlert {
  message: string;
  requestId?: string;
}

export function LoginPage(): JSX.Element {
  const { isAuthenticated, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const [alert, setAlert] = useState<FormAlert | null>(null);

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({ resolver: zodResolver(loginSchema) });

  if (isAuthenticated) {
    return <Navigate to={routes.dashboard} replace />;
  }

  const from =
    (location.state as { from?: { pathname?: string } } | null)?.from?.pathname ??
    routes.dashboard;
  const expired = searchParams.get('reason') === 'expired';

  const onSubmit = handleSubmit(async (values) => {
    setAlert(null);
    try {
      await login(values);
      navigate(from, { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.isValidation() && (err.field === 'email' || err.field === 'password')) {
          setError(err.field, { message: err.message });
        } else if (err.httpStatus === 401) {
          // Deliberately vague — the Backend returns one code for both cases.
          setAlert({ message: 'Invalid email or password.' });
        } else {
          setAlert({ message: err.message, requestId: err.requestId });
        }
      } else {
        setAlert({ message: 'Something went wrong. Please try again.' });
      }
    }
  });

  return (
    <form className="auth-card" onSubmit={onSubmit} noValidate>
      <div className="eyebrow">Welcome back</div>
      <h1>Sign in to your workspace</h1>
      <div className="sub">Use your work email to access the inventory workspace.</div>

      {expired && <AuthAlert tone="info" message="Your session expired. Please sign in again." />}
      {alert && <AuthAlert tone="danger" message={alert.message} requestId={alert.requestId} />}

      <Field label="Work email" htmlFor="email" required error={errors.email?.message}>
        <Input
          id="email"
          type="email"
          autoComplete="email"
          placeholder="you@company.com"
          invalid={!!errors.email}
          {...register('email')}
        />
      </Field>

      <Field label="Password" htmlFor="password" required error={errors.password?.message}>
        <PasswordInput
          id="password"
          autoComplete="current-password"
          placeholder="••••••••"
          invalid={!!errors.password}
          {...register('password')}
        />
      </Field>

      <Button variant="pri" type="submit" loading={isSubmitting}>
        Sign in
      </Button>

      <div className="signup">
        Need an account? <Link to={routes.register}>Create one</Link>
      </div>
    </form>
  );
}
