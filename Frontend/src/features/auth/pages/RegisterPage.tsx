import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Link, Navigate, useNavigate } from 'react-router-dom';
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

const registerSchema = z
  .object({
    full_name: z.string().min(1, 'Your name is required'),
    email: z.string().min(1, 'Email is required').email('Enter a valid email address'),
    password: z.string().min(8, 'Use at least 8 characters'),
    confirm_password: z.string().min(1, 'Please confirm your password'),
  })
  .refine((v) => v.password === v.confirm_password, {
    message: 'Passwords do not match',
    path: ['confirm_password'],
  });

type RegisterValues = z.infer<typeof registerSchema>;

interface FormAlert {
  message: string;
  requestId?: string;
}

export function RegisterPage(): JSX.Element {
  const { isAuthenticated, register: signUp } = useAuth();
  const navigate = useNavigate();
  const [alert, setAlert] = useState<FormAlert | null>(null);

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<RegisterValues>({ resolver: zodResolver(registerSchema) });

  if (isAuthenticated) {
    return <Navigate to={routes.dashboard} replace />;
  }

  const onSubmit = handleSubmit(async (values) => {
    setAlert(null);
    try {
      await signUp({
        full_name: values.full_name,
        email: values.email,
        password: values.password,
      });
      navigate(routes.dashboard, { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.code === 'EMAIL_ALREADY_REGISTERED') {
          setError('email', { message: 'This email is already registered.' });
        } else if (
          err.isValidation() &&
          (err.field === 'full_name' || err.field === 'email' || err.field === 'password')
        ) {
          setError(err.field, { message: err.message });
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
      <div className="eyebrow">Get started</div>
      <h1>Create your account</h1>
      <div className="sub">Set up your operations login for the inventory workspace.</div>

      {alert && <AuthAlert tone="danger" message={alert.message} requestId={alert.requestId} />}

      <Field label="Full name" htmlFor="full_name" required error={errors.full_name?.message}>
        <Input
          id="full_name"
          autoComplete="name"
          placeholder="Ravi Menon"
          invalid={!!errors.full_name}
          {...register('full_name')}
        />
      </Field>

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

      <Field
        label="Password"
        htmlFor="password"
        required
        hint="At least 8 characters."
        error={errors.password?.message}
      >
        <PasswordInput
          id="password"
          autoComplete="new-password"
          placeholder="••••••••"
          invalid={!!errors.password}
          {...register('password')}
        />
      </Field>

      <Field
        label="Confirm password"
        htmlFor="confirm_password"
        required
        error={errors.confirm_password?.message}
      >
        <PasswordInput
          id="confirm_password"
          autoComplete="new-password"
          placeholder="••••••••"
          invalid={!!errors.confirm_password}
          {...register('confirm_password')}
        />
      </Field>

      <Button variant="pri" type="submit" loading={isSubmitting}>
        Create account
      </Button>

      <div className="signup">
        Already have an account? <Link to={routes.login}>Sign in</Link>
      </div>
    </form>
  );
}
