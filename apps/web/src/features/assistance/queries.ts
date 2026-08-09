import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  completeAssistance,
  confirmAssistanceAction,
  consentToAssistance,
  createAssistanceInvitation,
  draftAssistanceAction,
  executeAssistanceAction,
  getAssistanceReceipt,
  getCitizenAssistanceActions,
  getCitizenAssistanceSession,
  getHelperAssistanceActions,
  getHelperAssistanceSession,
  pauseAssistance,
  redeemAssistanceInvitation,
  revokeAssistance,
} from "@/lib/api";

export function assistanceQueryKey(assistanceId: string) {
  return ["assistance-session", assistanceId] as const;
}

export function assistanceReceiptQueryKey(assistanceId: string) {
  return ["assistance-receipt", assistanceId] as const;
}

export function assistanceActionsQueryKey(assistanceId: string, helper: boolean) {
  return ["assistance-actions", assistanceId, helper ? "helper" : "citizen"] as const;
}

export function useCreateAssistanceInvitationMutation() {
  return useMutation({ mutationFn: createAssistanceInvitation });
}

export function useCitizenAssistanceQuery(assistanceId: string) {
  return useQuery({
    queryKey: assistanceQueryKey(assistanceId),
    queryFn: () => getCitizenAssistanceSession(assistanceId),
    enabled: Boolean(assistanceId),
    retry: false,
    refetchInterval: (query) =>
      query.state.data?.status === "awaiting_citizen_consent" ? 4_000 : false,
  });
}

export function useConsentAssistanceMutation(assistanceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => consentToAssistance(assistanceId),
    onSuccess: (session) => {
      queryClient.setQueryData(assistanceQueryKey(assistanceId), session);
    },
  });
}

export function useRevokeAssistanceMutation(assistanceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => revokeAssistance(assistanceId),
    onSuccess: (session) => {
      queryClient.setQueryData(assistanceQueryKey(assistanceId), session);
      void queryClient.invalidateQueries({ queryKey: assistanceReceiptQueryKey(assistanceId) });
    },
  });
}

export function useConfirmAssistanceActionMutation(assistanceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (actionId: string) => confirmAssistanceAction(assistanceId, actionId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: assistanceActionsQueryKey(assistanceId, false) });
    },
  });
}

export function useAssistanceReceiptQuery(assistanceId: string, enabled: boolean) {
  return useQuery({
    queryKey: assistanceReceiptQueryKey(assistanceId),
    queryFn: () => getAssistanceReceipt(assistanceId),
    enabled: Boolean(assistanceId) && enabled,
    retry: false,
  });
}

export function useCitizenAssistanceActionsQuery(assistanceId: string, enabled: boolean) {
  return useQuery({
    queryKey: assistanceActionsQueryKey(assistanceId, false),
    queryFn: () => getCitizenAssistanceActions(assistanceId),
    enabled: Boolean(assistanceId) && enabled,
    retry: false,
    refetchInterval: enabled ? 3_000 : false,
  });
}

export function useRedeemAssistanceMutation() {
  return useMutation({
    mutationFn: (input: { invitationToken: string; adminToken: string }) =>
      redeemAssistanceInvitation(input.invitationToken, input.adminToken),
  });
}

export function useHelperAssistanceQuery(
  assistanceId: string,
  adminToken: string,
  enabled: boolean,
) {
  return useQuery({
    queryKey: ["helper-assistance-session", assistanceId, Boolean(adminToken)],
    queryFn: () => getHelperAssistanceSession(assistanceId, adminToken),
    enabled: Boolean(assistanceId && adminToken) && enabled,
    retry: false,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "awaiting_citizen_consent" || status === "active" ? 3_000 : false;
    },
  });
}

export function useHelperAssistanceActionsQuery(
  assistanceId: string,
  adminToken: string,
  enabled: boolean,
) {
  return useQuery({
    queryKey: assistanceActionsQueryKey(assistanceId, true),
    queryFn: () => getHelperAssistanceActions(assistanceId, adminToken),
    enabled: Boolean(assistanceId && adminToken) && enabled,
    retry: false,
    refetchInterval: enabled ? 3_000 : false,
  });
}

export function useDraftAssistanceActionMutation(
  assistanceId: string,
  adminToken: string,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: Parameters<typeof draftAssistanceAction>[1]) =>
      draftAssistanceAction(assistanceId, input, adminToken),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["helper-assistance-session", assistanceId] });
    },
  });
}

export function useExecuteAssistanceActionMutation(
  assistanceId: string,
  adminToken: string,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (actionId: string) => executeAssistanceAction(assistanceId, actionId, adminToken),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["helper-assistance-session", assistanceId] });
    },
  });
}

export function usePauseAssistanceMutation(assistanceId: string, adminToken: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => pauseAssistance(assistanceId, adminToken),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["helper-assistance-session", assistanceId] });
    },
  });
}

export function useCompleteAssistanceMutation(assistanceId: string, adminToken: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => completeAssistance(assistanceId, adminToken),
    onSuccess: (receipt) => {
      queryClient.setQueryData(assistanceReceiptQueryKey(assistanceId), receipt);
      void queryClient.invalidateQueries({ queryKey: ["helper-assistance-session", assistanceId] });
    },
  });
}
