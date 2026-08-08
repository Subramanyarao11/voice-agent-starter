import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  getAdminAuditEvents,
  getAdminConversations,
  getAdminBenefitReports,
  getAdminEscalations,
  getAdminImports,
  getAdminLanguages,
  getAdminMe,
  getAdminOverview,
  getAdminNotifications,
  getAdminFreshness,
  getAdminEvaluations,
  getAdminFeatureFlags,
  getAdminProviders,
  getAdminReviews,
  getAdminSystem,
  getAdminTelemetry,
  downloadAdminAuditEvents,
  rollbackAdminProviderPolicy,
  rollbackAdminFeatureFlag,
  addAdminEscalationNote,
  claimAdminEscalation,
  routeAdminEscalation,
  resolveAdminEscalation,
  reviewAdminBenefit,
  updateAdminProviderPolicy,
  updateAdminFeatureFlag,
  updateAdminBenefitReport,
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

export function useAdminBenefitReportsQuery(token: string) {
  return useQuery({
    queryKey: ["admin", "benefit-reports"],
    queryFn: () => getAdminBenefitReports(token),
    enabled: Boolean(token),
  });
}

export function useUpdateAdminBenefitReportMutation(token: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      reportId: string;
      status: "acknowledged" | "resolved" | "dismissed";
      reason: string;
    }) => updateAdminBenefitReport(token, input.reportId, {
      status: input.status,
      reason: input.reason,
    }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin", "benefit-reports"] });
      void queryClient.invalidateQueries({ queryKey: ["admin", "audit"] });
    },
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
    refetchInterval: 30_000,
  });
}

export function useAdminNotificationsQuery(token: string) {
  return useQuery({
    queryKey: ["admin", "notifications"],
    queryFn: () => getAdminNotifications(token),
    enabled: Boolean(token),
    refetchInterval: 30_000,
  });
}

export function useAdminFreshnessQuery(token: string) {
  return useQuery({
    queryKey: ["admin", "freshness"],
    queryFn: () => getAdminFreshness(token),
    enabled: Boolean(token),
    refetchInterval: 60_000,
  });
}

export function useAdminEvaluationsQuery(token: string) {
  return useQuery({
    queryKey: ["admin", "evaluations"],
    queryFn: () => getAdminEvaluations(token),
    enabled: Boolean(token),
    refetchInterval: 60_000,
  });
}

export function useAdminFeatureFlagsQuery(token: string) {
  return useQuery({
    queryKey: ["admin", "feature-flags"],
    queryFn: () => getAdminFeatureFlags(token),
    enabled: Boolean(token),
  });
}

export function useUpdateAdminFeatureFlagMutation(token: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { key: string; payload: Parameters<typeof updateAdminFeatureFlag>[2] }) =>
      updateAdminFeatureFlag(token, input.key, input.payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({queryKey: ["admin", "feature-flags"]});
      void queryClient.invalidateQueries({queryKey: ["admin", "audit"]});
    },
  });
}

export function useRollbackAdminFeatureFlagMutation(token: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { key: string; reason: string }) =>
      rollbackAdminFeatureFlag(token, input.key, input.reason),
    onSuccess: () => {
      void queryClient.invalidateQueries({queryKey: ["admin", "feature-flags"]});
      void queryClient.invalidateQueries({queryKey: ["admin", "audit"]});
    },
  });
}

export function useUpdateAdminProviderPolicyMutation(token: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      provider: string;
      scope: string;
      payload: Parameters<typeof updateAdminProviderPolicy>[3];
    }) => updateAdminProviderPolicy(token, input.provider, input.scope, input.payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({queryKey: ["admin", "providers"]});
      void queryClient.invalidateQueries({queryKey: ["admin", "audit"]});
      void queryClient.invalidateQueries({queryKey: ["admin", "overview"]});
    },
  });
}

export function useRollbackAdminProviderPolicyMutation(token: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { provider: string; scope: string; reason: string }) =>
      rollbackAdminProviderPolicy(token, input.provider, input.scope, input.reason),
    onSuccess: () => {
      void queryClient.invalidateQueries({queryKey: ["admin", "providers"]});
      void queryClient.invalidateQueries({queryKey: ["admin", "audit"]});
      void queryClient.invalidateQueries({queryKey: ["admin", "overview"]});
    },
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

export function useDownloadAdminAuditMutation(token: string) {
  return useMutation({
    mutationFn: (format: "csv" | "json" = "csv") => downloadAdminAuditEvents(token, format),
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
    mutationFn: (input: { ticketId: string; resolution_code: string; note: string }) =>
      resolveAdminEscalation(token, input.ticketId, {
        resolution_code: input.resolution_code,
        note: input.note,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({queryKey: ["admin", "escalations"]});
      void queryClient.invalidateQueries({queryKey: ["admin", "overview"]});
    },
  });
}

export function useClaimAdminEscalationMutation(token: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (ticketId: string) => claimAdminEscalation(token, ticketId),
    onSuccess: () => {
      void queryClient.invalidateQueries({queryKey: ["admin", "escalations"]});
      void queryClient.invalidateQueries({queryKey: ["admin", "overview"]});
      void queryClient.invalidateQueries({queryKey: ["admin", "audit"]});
    },
  });
}

export function useAddAdminEscalationNoteMutation(token: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { ticketId: string; text: string }) =>
      addAdminEscalationNote(token, input.ticketId, input.text),
    onSuccess: () => {
      void queryClient.invalidateQueries({queryKey: ["admin", "escalations"]});
      void queryClient.invalidateQueries({queryKey: ["admin", "audit"]});
    },
  });
}

export function useRouteAdminEscalationMutation(token: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { ticketId: string; department: string; routing_location: string }) =>
      routeAdminEscalation(token, input.ticketId, {
        department: input.department,
        routing_location: input.routing_location,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({queryKey: ["admin", "escalations"]});
      void queryClient.invalidateQueries({queryKey: ["admin", "audit"]});
    },
  });
}
