export interface ActivitySubject {
  customerId?: string;
  leadId?: string;
}

export const activityKeys = {
  all: ['activities'] as const,
  list: (subject: ActivitySubject) =>
    ['activities', 'list', subject.customerId ?? null, subject.leadId ?? null] as const,
};
