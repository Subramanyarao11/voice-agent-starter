import { useMutation, useQuery } from "@tanstack/react-query";

import { getBenefit, reportBenefitIssue } from "@/lib/api";

export function benefitDetailQueryKey(benefitId: string) {
  return ["benefit-detail", benefitId] as const;
}

export function useBenefitDetailQuery(benefitId: string) {
  return useQuery({
    queryKey: benefitDetailQueryKey(benefitId),
    queryFn: () => getBenefit(benefitId),
    enabled: Boolean(benefitId),
    staleTime: 5 * 60 * 1000,
  });
}

export function useReportBenefitIssueMutation(benefitId: string, accessToken: string) {
  return useMutation({
    mutationFn: (payload: { category: string; description: string }) =>
      reportBenefitIssue(benefitId, payload, accessToken),
  });
}
