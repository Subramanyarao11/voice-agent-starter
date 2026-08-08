import { create } from "zustand";

const MAX_COMPARE_ITEMS = 3;

type CompareStore = {
  benefitIds: string[];
  toggle: (benefitId: string) => void;
  remove: (benefitId: string) => void;
  clear: () => void;
};

export const useCompareStore = create<CompareStore>((set) => ({
  benefitIds: [],
  toggle: (benefitId) =>
    set((state) => ({
      benefitIds: state.benefitIds.includes(benefitId)
        ? state.benefitIds.filter((id) => id !== benefitId)
        : state.benefitIds.length >= MAX_COMPARE_ITEMS
          ? state.benefitIds
          : [...state.benefitIds, benefitId],
    })),
  remove: (benefitId) =>
    set((state) => ({ benefitIds: state.benefitIds.filter((id) => id !== benefitId) })),
  clear: () => set({ benefitIds: [] }),
}));

export { MAX_COMPARE_ITEMS };
