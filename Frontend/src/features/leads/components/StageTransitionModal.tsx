import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';

import { useToast } from '@/components/toast/useToast';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { Textarea } from '@/components/ui/Textarea';
import { useApiError } from '@/hooks/useApiError';
import type { StageTransitionRequest } from '@/types/api.types';
import { LeadStage } from '@/types/enums';

import { transitionSchema, type TransitionValues } from '../lead.schema';
import { ALLOWED_TRANSITIONS } from '../lead.transitions';
import { useTransitionLead } from '../hooks/useLeads';

const STAGE_LABEL: Record<LeadStage, string> = {
  [LeadStage.NEW]: 'New',
  [LeadStage.QUALIFICATION]: 'Qualification',
  [LeadStage.NEGOTIATION]: 'Negotiation',
  [LeadStage.WON]: 'Won',
  [LeadStage.LOST]: 'Lost',
};

export interface StageTransitionModalProps {
  leadId: string;
  currentStage: LeadStage;
  onClose: () => void;
}

export function StageTransitionModal({
  leadId,
  currentStage,
  onClose,
}: StageTransitionModalProps): JSX.Element {
  const toast = useToast();
  const reportApiError = useApiError();
  const transitionMut = useTransitionLead(leadId);
  const allowed = ALLOWED_TRANSITIONS[currentStage];

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<TransitionValues>({
    resolver: zodResolver(transitionSchema),
    defaultValues: {
      to_stage: allowed[0],
      remark: '',
      won_value: '',
      lost_reason: '',
    },
  });

  const toStage = watch('to_stage');

  const onValid = (values: TransitionValues): void => {
    const body: StageTransitionRequest = { to_stage: values.to_stage };
    if (values.remark.trim()) body.remark = values.remark.trim();
    if (values.to_stage === LeadStage.WON) body.won_value = values.won_value.trim();
    if (values.to_stage === LeadStage.LOST) body.lost_reason = values.lost_reason.trim();

    transitionMut.mutate(body, {
      onSuccess: (lead) => {
        toast.success(`Lead moved to ${STAGE_LABEL[lead.stage]}.`);
        onClose();
      },
      onError: (error) => reportApiError(error, { scope: 'leads.transition' }),
    });
  };

  return (
    <Modal
      open
      onClose={onClose}
      title="Change stage"
      sub={`Currently ${STAGE_LABEL[currentStage]}`}
      footer={
        <>
          <Button variant="sec" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="pri"
            type="submit"
            form="stage-transition-form"
            loading={transitionMut.isPending}
          >
            Confirm
          </Button>
        </>
      }
    >
      <form
        id="stage-transition-form"
        className="flex col gap-16"
        onSubmit={handleSubmit(onValid)}
        noValidate
      >
        <Field label="Move to" htmlFor="to-stage" error={errors.to_stage?.message}>
          <select id="to-stage" className="select" {...register('to_stage')}>
            {allowed.map((s) => (
              <option key={s} value={s}>
                {STAGE_LABEL[s]}
              </option>
            ))}
          </select>
        </Field>

        {toStage === LeadStage.WON && (
          <Field label="Won value" htmlFor="won-value" required error={errors.won_value?.message}>
            <Input id="won-value" inputMode="decimal" {...register('won_value')} />
          </Field>
        )}
        {toStage === LeadStage.LOST && (
          <Field
            label="Lost reason"
            htmlFor="lost-reason"
            required
            error={errors.lost_reason?.message}
          >
            <Textarea id="lost-reason" rows={3} {...register('lost_reason')} />
          </Field>
        )}

        <Field label="Remark (optional)" htmlFor="remark" error={errors.remark?.message}>
          <Textarea id="remark" rows={2} {...register('remark')} />
        </Field>
      </form>
    </Modal>
  );
}
