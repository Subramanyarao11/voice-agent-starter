import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

type GuestSessionState = {
  sessionId: string;
  accessToken: string;
  expiresAt: string;
  setSession: (session: { session_id: string; access_token: string; expires_at: string }) => void;
  clearSession: () => void;
};

export const useGuestSessionStore = create<GuestSessionState>()(
  persist(
    (set) => ({
      sessionId: "",
      accessToken: "",
      expiresAt: "",
      setSession: (session) =>
        set({
          sessionId: session.session_id,
          accessToken: session.access_token,
          expiresAt: session.expires_at,
        }),
      clearSession: () => set({ sessionId: "", accessToken: "", expiresAt: "" }),
    }),
    {
      name: "sahaayak-guest-session",
      storage: createJSONStorage(() => sessionStorage),
      partialize: (state) => ({
        sessionId: state.sessionId,
        accessToken: state.accessToken,
        expiresAt: state.expiresAt,
      }),
    },
  ),
);
