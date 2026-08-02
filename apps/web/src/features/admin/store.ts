import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

type AdminSessionState = {
  token: string;
  setToken: (token: string) => void;
  clearToken: () => void;
};

export const useAdminSessionStore = create<AdminSessionState>()(
  persist(
    (set) => ({
      token: "",
      setToken: (token) => set({ token: token.trim() }),
      clearToken: () => set({ token: "" }),
    }),
    {
      name: "sahaayak-admin-session",
      storage: createJSONStorage(() => sessionStorage),
      partialize: (state) => ({ token: state.token }),
    },
  ),
);
