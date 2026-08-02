import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  getAdminAuditEvents,
  getAdminConversations,
  getAdminEscalations,
  getAdminImports,
  getAdminLanguages,
  getAdminMe,
  getAdminOverview,
  getAdminProviders,
  getAdminReviews,
  getAdminSystem,
  getAdminTelemetry,
  resolveAdminEscalation,
  reviewAdminBenefit,
} from "@/features/admin/api";

export function useAdminMeQuery(token: string) {
  return useQuery({
    queryKey: ["admin", "me", Boolean(token)],
    queryFn: () => getAdminMe(token),
    enabled: Boolean(token),
    retry: false,
  });
}

export function useAdminOverviewQuery(token: string) {
  return useQuery({
    queryKey: ["admin", "overview"],
    queryFn: () => getAdminOverview(token),
    enabled: Boolean(token),
    refetchInterval: 30_000,
  });
}

export function useAdminConversationsQuery(token: string) {
  return useQuery({
    queryKey: ["admin", "conversations"],
    queryFn: () => getAdminConversations(token),
    enabled: Boolean(token),
  });
}

export function useAdminTelemetryQuery(token: string) {
  return useQuery({
    queryKey: ["admin", "telemetry"],
    queryFn: () => getAdminTelemetry(token),
    enabled: Boolean(token),
  });
}

export function useAdminReviewsQuery(token: string) {
  return useQuery({
    queryKey: ["admin", "reviews"],
    queryFn: () => getAdminReviews(token),
    enabled: Boolean(token),
  });
}

export function useAdminEscalationsQuery(token: string) {
  return useQuery({
    queryKey: ["admin", "escalations"],
    queryFn: () => getAdminEscalations(token),
    enabled: Boolean(token),
  });
}

export function useAdminProvidersQuery(token: string) {
  return useQuery({
    queryKey: ["admin", "providers"],
    queryFn: () => getAdminProviders(token),
    enabled: Boolean(token),
  });
}

export function useAdminLanguagesQuery(token: string) {
  return useQuery({
    queryKey: ["admin", "languages"],
    queryFn: () => getAdminLanguages(token),
    enabled: Boolean(token),
  });
}

export function useAdminAuditQuery(token: string) {
  return useQuery({
    queryKey: ["admin", "audit"],
    queryFn: () => getAdminAuditEvents(token),
    enabled: Boolean(token),
  });
}

export function useAdminImportsQuery(token: string) {
  return useQuery({
    queryKey: ["admin", "imports"],
    queryFn: () => getAdminImports(token),
    enabled: Boolean(token),
  });
}

export function useAdminSystemQuery(token: string) {
  return useQuery({
    queryKey: ["admin", "system"],
    queryFn: () => getAdminSystem(token),
    enabled: Boolean(token),
  });
}

export function useReviewAdminBenefitMutation(token: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { benefitId: string; status: string; reason: string; activate: boolean }) =>
      reviewAdminBenefit(token, input.benefitId, {
        verification_status: input.status,
        reason: input.reason,
        activate: input.activate,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({queryKey: ["admin"]});
    },
  });
}

export function useResolveAdminEscalationMutation(token: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (ticketId: string) => resolveAdminEscalation(token, ticketId),
    onSuccess: () => {
      void queryClient.invalidateQueries({queryKey: ["admin", "escalations"]});
      void queryClient.invalidateQueries({queryKey: ["admin", "overview"]});
    },
  });
}
