import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

type AppTourState = {
  hasSeenTour: boolean;
  markTourSeen: () => void;
};

/** Persisted separately from the conversation so clearing a guest session does
 * not unexpectedly interrupt the one-time orientation. */
export const useAppTourStore = create<AppTourState>()(
  persist(
    (set) => ({
      hasSeenTour: false,
      markTourSeen: () => set({ hasSeenTour: true }),
    }),
    {
      name: "sahaayak-app-tour:v1",
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({ hasSeenTour: state.hasSeenTour }),
    },
  ),
);
