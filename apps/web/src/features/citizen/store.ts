import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

type CitizenWorkspaceState = {
  activeHouseholdId: string;
  activeMemberId: string;
  setActiveHousehold: (id: string) => void;
  setActiveMember: (id: string) => void;
  clearWorkspace: () => void;
};

export const useCitizenWorkspaceStore = create<CitizenWorkspaceState>()(
  persist(
    (set) => ({
      activeHouseholdId: "",
      activeMemberId: "",
      setActiveHousehold: (activeHouseholdId) => set({ activeHouseholdId }),
      setActiveMember: (activeMemberId) => set({ activeMemberId }),
      clearWorkspace: () => set({ activeHouseholdId: "", activeMemberId: "" }),
    }),
    {
      name: "sahaayak-citizen-workspace",
      storage: createJSONStorage(() => sessionStorage),
      partialize: (state) => ({
        activeHouseholdId: state.activeHouseholdId,
        activeMemberId: state.activeMemberId,
      }),
    },
  ),
);
