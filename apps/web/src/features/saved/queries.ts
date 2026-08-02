import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createReminder,
  getReminders,
  getSavedBenefits,
  removeSavedBenefit,
  saveBenefit,
} from "@/lib/api";

export function savedBenefitsQueryKey(sessionId: string) {
  return ["saved-benefits", sessionId] as const;
}

export function useSavedBenefitsQuery(sessionId: string, accessToken: string) {
  return useQuery({
    queryKey: savedBenefitsQueryKey(sessionId),
    queryFn: () => getSavedBenefits(sessionId, accessToken),
    enabled: Boolean(sessionId && accessToken),
  });
}

export function useSaveBenefitMutation(sessionId: string, accessToken: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (benefitId: string) => saveBenefit(sessionId, benefitId, accessToken),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: savedBenefitsQueryKey(sessionId) }),
  });
}

export function useRemoveSavedBenefitMutation(sessionId: string, accessToken: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (benefitId: string) => removeSavedBenefit(sessionId, benefitId, accessToken),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: savedBenefitsQueryKey(sessionId) }),
  });
}

export function useRemindersQuery(sessionId: string, accessToken: string) {
  return useQuery({
    queryKey: ["reminders", sessionId],
    queryFn: () => getReminders(sessionId, accessToken),
    enabled: Boolean(sessionId && accessToken),
  });
}

export function useCreateReminderMutation(sessionId: string, accessToken: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { benefit_id: string; due_at: string; note?: string }) =>
      createReminder(sessionId, payload, accessToken),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["reminders", sessionId] }),
  });
}
