import { create } from "zustand";
import { persist } from "zustand/middleware";

type PwaPreferences = {
  dataSaver: boolean;
  setDataSaver: (enabled: boolean) => void;
};

export const usePwaPreferences = create<PwaPreferences>()(
  persist(
    (set) => ({
      dataSaver: false,
      setDataSaver: (dataSaver) => set({ dataSaver }),
    }),
    { name: "sahaayak-pwa-preferences" },
  ),
);
