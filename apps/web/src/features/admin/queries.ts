import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  getAdminAuditEvents,
  getAdminConversations,
  getAdminDirectory,
  getAdminDirectoryVersions,
  getAdminBenefitReports,
  getAdminEscalations,
  getAdminImports,
  getAdminLanguages,
  getAdminMe,
  getAdminOverview,
  getAdminNotifications,
  getAdminFreshness,
  getAdminBenefitVersions,
  getAdminEvaluations,
  getAdminFeatureFlags,
  getAdminDeploymentComparison,
  getAdminProviderFailureSimulations,
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
  rollbackAdminBenefit,
  updateAdminBenefit,
  updateFreshnessAlert,
  updateAdminProviderPolicy,
  updateAdminFeatureFlag,
  updateAdminBenefitReport,
  updateAdminLanguageReview,
  approveAdminDirectoryEntry,
  deactivateAdminDirectoryEntry,
  rollbackAdminDirectoryEntry,
  updateAdminDirectoryEntry,
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

export function useAdminDirectoryQuery(token: string) {
  return useQuery({
    queryKey: ["admin", "directory"],
    queryFn: () => getAdminDirectory(token),
    enabled: Boolean(token),
  });
}

export function useApproveAdminDirectoryMutation(token: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: {entryId: string; reason: string}) =>
      approveAdminDirectoryEntry(token, input.entryId, input.reason),
    onSuccess: () => {
      void queryClient.invalidateQueries({queryKey: ["admin", "directory"]});
      void queryClient.invalidateQueries({queryKey: ["admin", "escalations"]});
      void queryClient.invalidateQueries({queryKey: ["admin", "audit"]});
    },
  });
}

export function useDeactivateAdminDirectoryMutation(token: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: {entryId: string; reason: string}) =>
      deactivateAdminDirectoryEntry(token, input.entryId, input.reason),
    onSuccess: () => {
      void queryClient.invalidateQueries({queryKey: ["admin", "directory"]});
      void queryClient.invalidateQueries({queryKey: ["admin", "escalations"]});
      void queryClient.invalidateQueries({queryKey: ["admin", "audit"]});
    },
  });
}

export function useAdminDirectoryVersionsQuery(token: string, entryId: string, enabled = true) {
  return useQuery({
    queryKey: ["admin", "directory-versions", entryId],
    queryFn: () => getAdminDirectoryVersions(token, entryId),
    enabled: Boolean(token) && enabled,
  });
}

export function useUpdateAdminDirectoryMutation(token: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: {entryId: string; payload: Parameters<typeof updateAdminDirectoryEntry>[2]}) =>
      updateAdminDirectoryEntry(token, input.entryId, input.payload),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({queryKey: ["admin", "directory"]});
      void queryClient.invalidateQueries({queryKey: ["admin", "directory-versions", variables.entryId]});
      void queryClient.invalidateQueries({queryKey: ["admin", "freshness"]});
      void queryClient.invalidateQueries({queryKey: ["admin", "audit"]});
    },
  });
}

export function useRollbackAdminDirectoryMutation(token: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: {entryId: string; version: number; reason: string}) =>
      rollbackAdminDirectoryEntry(token, input.entryId, {
        version: input.version,
        reason: input.reason,
      }),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({queryKey: ["admin", "directory"]});
      void queryClient.invalidateQueries({queryKey: ["admin", "directory-versions", variables.entryId]});
      void queryClient.invalidateQueries({queryKey: ["admin", "freshness"]});
      void queryClient.invalidateQueries({queryKey: ["admin", "audit"]});
    },
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

export function useAdminProviderFailureSimulationsQuery(token: string) {
  return useQuery({
    queryKey: ["admin", "provider-failure-simulations", "en", "KA"],
    queryFn: () => getAdminProviderFailureSimulations(token),
    enabled: Boolean(token),
    refetchInterval: 60_000,
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

export function useAdminBenefitVersionsQuery(token: string, benefitId: string, enabled = true) {
  return useQuery({
    queryKey: ["admin", "benefit-versions", benefitId],
    queryFn: () => getAdminBenefitVersions(token, benefitId),
    enabled: Boolean(token) && enabled,
  });
}

export function useUpdateAdminBenefitMutation(token: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { benefitId: string; payload: Parameters<typeof updateAdminBenefit>[2] }) =>
      updateAdminBenefit(token, input.benefitId, input.payload),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({queryKey: ["admin", "reviews"]});
      void queryClient.invalidateQueries({queryKey: ["admin", "benefit-versions", variables.benefitId]});
      void queryClient.invalidateQueries({queryKey: ["admin", "freshness"]});
      void queryClient.invalidateQueries({queryKey: ["admin", "audit"]});
    },
  });
}

export function useRollbackAdminBenefitMutation(token: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { benefitId: string; version: number; reason: string }) =>
      rollbackAdminBenefit(token, input.benefitId, {
        version: input.version,
        reason: input.reason,
      }),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({queryKey: ["admin", "reviews"]});
      void queryClient.invalidateQueries({queryKey: ["admin", "benefit-versions", variables.benefitId]});
      void queryClient.invalidateQueries({queryKey: ["admin", "freshness"]});
      void queryClient.invalidateQueries({queryKey: ["admin", "audit"]});
    },
  });
}

export function useUpdateFreshnessAlertMutation(token: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { alertId: string; status: "acknowledged" | "resolved"; reason: string }) =>
      updateFreshnessAlert(token, input.alertId, {
        status: input.status,
        reason: input.reason,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({queryKey: ["admin", "freshness"]});
      void queryClient.invalidateQueries({queryKey: ["admin", "audit"]});
    },
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

export function useUpdateAdminLanguageReviewMutation(token: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: {code: string; payload: Parameters<typeof updateAdminLanguageReview>[2]}) =>
      updateAdminLanguageReview(token, input.code, input.payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({queryKey: ["admin", "languages"]});
      void queryClient.invalidateQueries({queryKey: ["admin", "flags"]});
      void queryClient.invalidateQueries({queryKey: ["admin", "audit"]});
      void queryClient.invalidateQueries({queryKey: ["catalog"]});
    },
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

export function useAdminDeploymentComparisonQuery(token: string) {
  return useQuery({
    queryKey: ["admin", "deployment-comparison"],
    queryFn: () => getAdminDeploymentComparison(token),
    enabled: Boolean(token),
    refetchInterval: 60_000,
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
