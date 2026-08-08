import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  cancelReminder,
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
    refetchInterval: (query) =>
      query.state.data?.some(
        (reminder) => reminder.status === "scheduled" && reminder.channel !== "in_app",
      )
        ? 15_000
        : false,
  });
}

export function useCreateReminderMutation(sessionId: string, accessToken: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { benefit_id: string; due_at: string; note?: string; channel?: string }) =>
      createReminder(sessionId, payload, accessToken),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["reminders", sessionId] }),
  });
}

export function useCancelReminderMutation(sessionId: string, accessToken: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (reminderId: string) => cancelReminder(sessionId, reminderId, accessToken),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["reminders", sessionId] }),
  });
}
