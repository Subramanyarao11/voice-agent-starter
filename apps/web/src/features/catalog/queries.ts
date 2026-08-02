import { useQuery } from "@tanstack/react-query";

import { getCatalog, getHealth } from "@/lib/api";

export const catalogQueryKey = ["catalog"] as const;
export const healthQueryKey = ["health"] as const;

export function useCatalogQuery() {
  return useQuery({
    queryKey: catalogQueryKey,
    queryFn: getCatalog,
    staleTime: 60_000,
  });
}

export function useHealthQuery() {
  return useQuery({
    queryKey: healthQueryKey,
    queryFn: getHealth,
    refetchInterval: 30_000,
    staleTime: 10_000,
  });
}
