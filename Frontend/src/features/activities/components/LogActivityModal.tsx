import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';

import { useToast } from '@/components/toast/useToast';
import { Button } from '@/components/ui/Button';
import { Drawer } from '@/components/ui/Drawer';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Textarea } from '@/components/ui/Textarea';
import { useApiError } from '@/hooks/useApiError';
import type { ActivityCreateRequest } from '@/types/api.types';
import { ActivityType } from '@/types/enums';

import { EMPTY_ACTIVITY, activitySchema, type ActivityValues } from '../activity.schema';
import { useLogActivity } from '../hooks/useActivities';

const FORM_ID = 'log-activity-form';

const TYPE_LABELS: Record<ActivityType, string> = {
  [ActivityType.VISIT]: 'Visit',
  [ActivityType.MEETING]: 'Meeting',
  [ActivityType.FOLLOW_UP]: 'Follow-up',
  [ActivityType.CALL]: 'Call',
  [ActivityType.COMPLAINT]: 'Complaint',
};

export interface LogActivityModalProps {
  customerId?: string;
  leadId?: string;
  onClose: () => void;
}

export function LogActivityModal({
  customerId,
  leadId,
  onClose,
}: LogActivityModalProps): JSX.Element {
  const toast = useToast();
  const reportApiError = useApiError();
  const logMut = useLogActivity({ customerId, leadId });

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ActivityValues>({
    resolver: zodResolver(activitySchema),
    defaultValues: EMPTY_ACTIVITY,
  });

  const onValid = (values: ActivityValues): void => {
    const body: ActivityCreateRequest = {
      type: values.type,
      occurred_at: new Date(values.occurred_at).toISOString(),
    };
    if (customerId) body.customer_id = customerId;
    if (leadId) body.lead_id = leadId;
    if (values.duration_minutes) body.duration_minutes = Number(values.duration_minutes);
    const remarks = values.remarks?.trim();
    if (remarks) body.remarks = remarks;

    logMut.mutate(body, {
      onSuccess: () => {
        toast.success('Activity logged.');
        onClose();
      },
      onError: (error) =>
        reportApiError(error, {
          scope: 'activities.create',
          fallbackMessage: 'Could not log the activity.',
        }),
    });
  };

  return (
    <Drawer open onClose={onClose} title="Log Activity">
      <form id={FORM_ID} className="flex col gap-16" onSubmit={handleSubmit(onValid)} noValidate>
        <Field label="Type" htmlFor="act-type" required error={errors.type?.message}>
          <Select id="act-type" invalid={!!errors.type} {...register('type')}>
            {Object.values(ActivityType).map((value) => (
              <option key={value} value={value}>
                {TYPE_LABELS[value]}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="When" htmlFor="act-when" required error={errors.occurred_at?.message}>
          <Input
            id="act-when"
            type="datetime-local"
            invalid={!!errors.occurred_at}
            {...register('occurred_at')}
          />
        </Field>
        <Field
          label="Duration (minutes)"
          htmlFor="act-duration"
          error={errors.duration_minutes?.message}
        >
          <Input
            id="act-duration"
            type="number"
            min={1}
            invalid={!!errors.duration_minutes}
            {...register('duration_minutes')}
          />
        </Field>
        <Field label="Remarks" htmlFor="act-remarks" error={errors.remarks?.message}>
          <Textarea id="act-remarks" rows={3} {...register('remarks')} />
        </Field>

        <div className="drawer-foot">
          <Button variant="sec" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="pri" type="submit" loading={logMut.isPending}>
            Log activity
          </Button>
        </div>
      </form>
    </Drawer>
  );
}
