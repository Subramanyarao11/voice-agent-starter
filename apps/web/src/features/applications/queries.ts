import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createApplication,
  getApplicationFields,
  getApplicationOutcome,
  getApplicationRequirements,
  getApplication,
  getApplications,
  previewApplicationPack,
  recordApplicationOutcome,
  recordApplicationStatus,
  updateApplicationField,
  updateApplicationRequirement,
} from "@/lib/api";

export function applicationsQueryKey(sessionId: string) {
  return ["applications", sessionId] as const;
}

export function applicationQueryKey(sessionId: string, applicationId: string) {
  return ["application", sessionId, applicationId] as const;
}

export function useApplicationsQuery(sessionId: string, accessToken: string) {
  return useQuery({
    queryKey: applicationsQueryKey(sessionId),
    queryFn: () => getApplications(sessionId, accessToken),
    enabled: Boolean(sessionId && accessToken),
  });
}

export function useApplicationQuery(
  sessionId: string,
  applicationId: string,
  accessToken: string,
) {
  return useQuery({
    queryKey: applicationQueryKey(sessionId, applicationId),
    queryFn: () => getApplication(sessionId, applicationId, accessToken),
    enabled: Boolean(sessionId && applicationId && accessToken),
  });
}

export function useCreateApplicationMutation(sessionId: string, accessToken: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { benefit_id: string; application_channel?: string }) =>
      createApplication(sessionId, payload, accessToken),
    onSuccess: (application) => {
      void queryClient.invalidateQueries({ queryKey: applicationsQueryKey(sessionId) });
      queryClient.setQueryData(applicationQueryKey(sessionId, application.id), application);
    },
  });
}

export function useRecordApplicationStatusMutation(
  sessionId: string,
  applicationId: string,
  accessToken: string,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      status: string;
      occurred_at?: string;
      submission_date?: string;
      external_reference?: string;
      reason_code?: string;
    }) => recordApplicationStatus(sessionId, applicationId, payload, accessToken),
    onSuccess: (application) => {
      queryClient.setQueryData(applicationQueryKey(sessionId, applicationId), application);
      void queryClient.invalidateQueries({ queryKey: applicationsQueryKey(sessionId) });
      void queryClient.invalidateQueries({ queryKey: ["application-tasks", sessionId] });
    },
  });
}

export function useApplicationPackPreviewQuery(
  sessionId: string,
  applicationId: string,
  accessToken: string,
) {
  return useQuery({
    queryKey: ["application-pack-preview", sessionId, applicationId],
    queryFn: () => previewApplicationPack(sessionId, applicationId, accessToken),
    enabled: Boolean(sessionId && applicationId && accessToken),
    staleTime: 10 * 60 * 1000,
  });
}

export function useApplicationFieldsQuery(
  sessionId: string,
  applicationId: string,
  accessToken: string,
) {
  return useQuery({
    queryKey: ["application-fields", sessionId, applicationId],
    queryFn: () => getApplicationFields(sessionId, applicationId, accessToken),
    enabled: Boolean(sessionId && applicationId && accessToken),
  });
}

export function useApplicationRequirementsQuery(
  sessionId: string,
  applicationId: string,
  accessToken: string,
) {
  return useQuery({
    queryKey: ["application-requirements", sessionId, applicationId],
    queryFn: () => getApplicationRequirements(sessionId, applicationId, accessToken),
    enabled: Boolean(sessionId && applicationId && accessToken),
  });
}

export function useUpdateApplicationFieldMutation(
  sessionId: string,
  applicationId: string,
  accessToken: string,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { fieldKey: string; value: string; expectedRevision?: number }) =>
      updateApplicationField(
        sessionId,
        applicationId,
        input.fieldKey,
        { value: input.value, expected_revision: input.expectedRevision },
        accessToken,
      ),
    onSuccess: (fields) => {
      queryClient.setQueryData(["application-fields", sessionId, applicationId], fields);
      void queryClient.invalidateQueries({ queryKey: applicationQueryKey(sessionId, applicationId) });
    },
  });
}

export function useUpdateApplicationRequirementMutation(
  sessionId: string,
  applicationId: string,
  accessToken: string,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      requirementKey: string;
      status: "missing" | "ready" | "not_applicable" | "submitted" | "needs_update";
      reason?: string;
      expectedCaseRevision?: number;
    }) =>
      updateApplicationRequirement(
        sessionId,
        applicationId,
        input.requirementKey,
        {
          status: input.status,
          reason: input.reason,
          expected_case_revision: input.expectedCaseRevision,
        },
        accessToken,
      ),
    onSuccess: (requirements) => {
      queryClient.setQueryData(["application-requirements", sessionId, applicationId], requirements);
      void queryClient.invalidateQueries({ queryKey: applicationQueryKey(sessionId, applicationId) });
    },
  });
}

export function useApplicationOutcomeQuery(
  sessionId: string,
  applicationId: string,
  accessToken: string,
) {
  return useQuery({
    queryKey: ["application-outcome", sessionId, applicationId],
    queryFn: () => getApplicationOutcome(sessionId, applicationId, accessToken),
    enabled: Boolean(sessionId && applicationId && accessToken),
    retry: (failureCount, error) => error instanceof Error && "status" in error && (error as { status: number }).status !== 404 && failureCount < 2,
  });
}

export function useRecordApplicationOutcomeMutation(
  sessionId: string,
  applicationId: string,
  accessToken: string,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      outcome: "received" | "not_received" | "partially_received" | "unknown";
      reason_code?: string;
      free_text?: string;
      satisfaction_score?: number;
      consent_for_evaluation?: boolean;
      expected_case_revision?: number;
    }) => recordApplicationOutcome(sessionId, applicationId, payload, accessToken),
    onSuccess: (outcome) => {
      queryClient.setQueryData(["application-outcome", sessionId, applicationId], outcome);
      void queryClient.invalidateQueries({ queryKey: applicationQueryKey(sessionId, applicationId) });
    },
  });
}
