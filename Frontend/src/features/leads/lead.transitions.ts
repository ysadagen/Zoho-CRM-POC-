import { LeadStage } from '@/types/enums';

/** Stages a lead can move *to* (NEW is only an initial state). */
export type TransitionTarget = Exclude<LeadStage, typeof LeadStage.NEW>;

/** Legal next stages per the Backend state machine (§3.2). Terminal stages
 *  map to none — the caller hides the trigger for those. */
export const ALLOWED_TRANSITIONS: Record<LeadStage, TransitionTarget[]> = {
  [LeadStage.NEW]: [LeadStage.QUALIFICATION, LeadStage.LOST],
  [LeadStage.QUALIFICATION]: [LeadStage.NEGOTIATION, LeadStage.LOST],
  [LeadStage.NEGOTIATION]: [LeadStage.WON, LeadStage.LOST],
  [LeadStage.WON]: [],
  [LeadStage.LOST]: [],
};
