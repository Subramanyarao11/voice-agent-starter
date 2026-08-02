import { useMutation } from "@tanstack/react-query";

import { createBrowserSession } from "@/lib/api";

export function useCreateBrowserSessionMutation() {
  return useMutation({
    mutationFn: (payload: { language_code?: string; state_code?: string }) =>
      createBrowserSession(payload),
  });
}
