import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';

import { useToast } from '@/components/toast/useToast';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { useApiError } from '@/hooks/useApiError';
import type { User } from '@/types/api.types';

import { useUpdateProfile } from '../hooks/useUpdateProfile';
import { editNameSchema, type EditNameValues } from '../settings.schema';

export interface EditNameModalProps {
  user: User;
  onClose: () => void;
}

export function EditNameModal({ user, onClose }: EditNameModalProps): JSX.Element {
  const toast = useToast();
  const reportApiError = useApiError();
  const updateMut = useUpdateProfile(user.id);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<EditNameValues>({
    resolver: zodResolver(editNameSchema),
    defaultValues: { full_name: user.full_name },
  });

  const onValid = (values: EditNameValues): void => {
    updateMut.mutate(values.full_name, {
      onSuccess: () => {
        toast.success('Name updated.');
        onClose();
      },
      onError: (error) =>
        reportApiError(error, { scope: 'settings.profile.update', fallbackMessage: 'Could not update your name.' }),
    });
  };

  return (
    <Modal open onClose={onClose} title="Edit name">
      <form className="flex col gap-16" onSubmit={handleSubmit(onValid)} noValidate>
        <Field label="Full name" htmlFor="profile-name" required error={errors.full_name?.message}>
          <Input id="profile-name" invalid={!!errors.full_name} {...register('full_name')} />
        </Field>
        <div className="flex justify-end gap-8">
          <Button variant="sec" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="pri" type="submit" loading={updateMut.isPending}>
            Save
          </Button>
        </div>
      </form>
    </Modal>
  );
}
