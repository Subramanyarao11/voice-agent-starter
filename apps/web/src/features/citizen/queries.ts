import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  addHouseholdMember,
  createHousehold,
  getCitizenMe,
  getHouseholdFacts,
  getHouseholdMembers,
  getHouseholdRadar,
  getHouseholds,
  getMemberFacts,
  refreshHouseholdRadar,
  updateHouseholdRadar,
  writeMemberFact,
} from "@/lib/api";

export const citizenMeQueryKey = ["citizen-me"] as const;
export const householdsQueryKey = ["citizen-households"] as const;

export function householdQueryKey(householdId: string) {
  return ["citizen-household", householdId] as const;
}

export function membersQueryKey(householdId: string) {
  return ["citizen-household-members", householdId] as const;
}

export function factsQueryKey(householdId: string, memberId: string | undefined) {
  return ["citizen-household-facts", householdId, memberId ?? "household"] as const;
}

export function radarQueryKey(householdId: string, memberId: string | undefined) {
  return ["citizen-household-radar", householdId, memberId ?? "all"] as const;
}

export function useCitizenMeQuery() {
  return useQuery({
    queryKey: citizenMeQueryKey,
    queryFn: getCitizenMe,
    retry: false,
    staleTime: 60_000,
  });
}

export function useHouseholdsQuery(enabled: boolean) {
  return useQuery({
    queryKey: householdsQueryKey,
    queryFn: getHouseholds,
    enabled,
    staleTime: 30_000,
  });
}

export function useCreateHouseholdMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createHousehold,
    onSuccess: (household) => {
      queryClient.setQueryData(householdsQueryKey, [household]);
      void queryClient.invalidateQueries({ queryKey: citizenMeQueryKey });
    },
  });
}

export function useMembersQuery(householdId: string) {
  return useQuery({
    queryKey: membersQueryKey(householdId),
    queryFn: () => getHouseholdMembers(householdId),
    enabled: Boolean(householdId),
    staleTime: 30_000,
  });
}

export function useAddMemberMutation(householdId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: Parameters<typeof addHouseholdMember>[1]) =>
      addHouseholdMember(householdId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: membersQueryKey(householdId) });
      void queryClient.invalidateQueries({ queryKey: householdsQueryKey });
    },
  });
}

export function useFactsQuery(householdId: string, memberId: string | undefined) {
  return useQuery({
    queryKey: factsQueryKey(householdId, memberId),
    queryFn: () => (memberId ? getMemberFacts(householdId, memberId) : getHouseholdFacts(householdId)),
    enabled: Boolean(householdId),
    staleTime: 30_000,
  });
}

export function useWriteMemberFactMutation(householdId: string, memberId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { factKey: string; value: string; purposes: string[]; expectedRevision?: number }) =>
      writeMemberFact(householdId, memberId, input.factKey, {
        value: input.value,
        purposes: input.purposes,
        confirm_purpose: true,
        expected_revision: input.expectedRevision,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: factsQueryKey(householdId, memberId) });
      void queryClient.invalidateQueries({ queryKey: radarQueryKey(householdId, memberId) });
    },
  });
}

export function useRadarQuery(householdId: string, memberId: string | undefined) {
  return useQuery({
    queryKey: radarQueryKey(householdId, memberId),
    queryFn: () => getHouseholdRadar(householdId, memberId),
    enabled: Boolean(householdId),
    staleTime: 30_000,
  });
}

export function useRefreshRadarMutation(householdId: string, memberId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => refreshHouseholdRadar(householdId, { member_id: memberId }),
    onSuccess: (radar) => {
      queryClient.setQueryData(radarQueryKey(householdId, memberId), {
        household_id: radar.household_id,
        generated_at: radar.generated_at,
        recommendations: radar.recommendations,
        counts_by_state: radar.counts_by_verdict,
      });
    },
  });
}

export function useRadarActionMutation(householdId: string, memberId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { recommendationId: string; action: "view" | "snooze" | "dismiss" }) =>
      updateHouseholdRadar(householdId, input.recommendationId, { action: input.action }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: radarQueryKey(householdId, memberId) });
    },
  });
}
