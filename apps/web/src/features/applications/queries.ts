import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createApplication,
  getApplication,
  getApplications,
  previewApplicationPack,
  recordApplicationStatus,
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
