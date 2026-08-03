import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  addContactPoint,
  getContactPoints,
  getNotificationChannels,
  revokeContactPoint,
  verifyContactPoint,
} from "@/lib/api";

export function contactPointsQueryKey(sessionId: string) {
  return ["contact-points", sessionId] as const;
}

export function notificationChannelsQueryKey(sessionId: string) {
  return ["notification-channels", sessionId] as const;
}

export function useContactPointsQuery(sessionId: string, accessToken: string) {
  return useQuery({
    queryKey: contactPointsQueryKey(sessionId),
    queryFn: () => getContactPoints(sessionId, accessToken),
    enabled: Boolean(sessionId && accessToken),
  });
}

/**
 * Which channels the caller can actually use, and why the others cannot.
 * Refetched after every contact change, because verifying a contact or
 * revoking one changes availability server-side.
 */
export function useNotificationChannelsQuery(sessionId: string, accessToken: string) {
  return useQuery({
    queryKey: notificationChannelsQueryKey(sessionId),
    queryFn: () => getNotificationChannels(sessionId, accessToken),
    enabled: Boolean(sessionId && accessToken),
  });
}

function useContactInvalidation(sessionId: string) {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: contactPointsQueryKey(sessionId) });
    queryClient.invalidateQueries({ queryKey: notificationChannelsQueryKey(sessionId) });
  };
}

export function useAddContactPointMutation(sessionId: string, accessToken: string) {
  const invalidate = useContactInvalidation(sessionId);
  return useMutation({
    mutationFn: (payload: {
      channel: string;
      destination: string;
      locale: string;
      consent: boolean;
    }) => addContactPoint(sessionId, payload, accessToken),
    onSuccess: invalidate,
  });
}

export function useVerifyContactPointMutation(sessionId: string, accessToken: string) {
  const invalidate = useContactInvalidation(sessionId);
  return useMutation({
    mutationFn: (payload: { contactId: string; code: string }) =>
      verifyContactPoint(sessionId, payload.contactId, payload.code, accessToken),
    onSuccess: invalidate,
  });
}

export function useRevokeContactPointMutation(sessionId: string, accessToken: string) {
  const invalidate = useContactInvalidation(sessionId);
  return useMutation({
    mutationFn: (contactId: string) => revokeContactPoint(sessionId, contactId, accessToken),
    onSuccess: invalidate,
  });
}
