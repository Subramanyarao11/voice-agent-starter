import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

type AdminSessionState = {
  token: string;
  idToken: string;
  expiresAt: number;
  setToken: (token: string) => void;
  setTokens: (tokens: { accessToken: string; idToken?: string; expiresAt: number }) => void;
  clearToken: () => void;
};

export const useAdminSessionStore = create<AdminSessionState>()(
  persist(
    (set) => ({
      token: "",
      idToken: "",
      expiresAt: 0,
      setToken: (token) => set({ token: token.trim(), idToken: "", expiresAt: 0 }),
      setTokens: ({ accessToken, idToken = "", expiresAt }) =>
        set({ token: accessToken.trim(), idToken, expiresAt }),
      clearToken: () => set({ token: "", idToken: "", expiresAt: 0 }),
    }),
    {
      name: "sahaayak-admin-session",
      storage: createJSONStorage(() => sessionStorage),
      partialize: (state) => ({ token: state.token, idToken: state.idToken, expiresAt: state.expiresAt }),
    },
  ),
);
