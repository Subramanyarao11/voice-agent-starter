import { useQuery } from "@tanstack/react-query";

import { getBenefit } from "@/lib/api";

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
