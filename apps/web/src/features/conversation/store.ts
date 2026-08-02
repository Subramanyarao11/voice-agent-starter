import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

import type { TurnResponse } from "@/lib/api";

export type ConversationMessage = {
  id: string;
  role: "caller" | "agent";
  text: string;
};

type ConversationStore = {
  languageCode: string;
  stateCode: string;
  draft: string;
  messages: ConversationMessage[];
  lastTurn: TurnResponse | null;
  setLanguageCode: (languageCode: string) => void;
  setStateCode: (stateCode: string) => void;
  setDraft: (draft: string) => void;
  appendTurn: (callerText: string, response: TurnResponse) => void;
  clearConversation: () => void;
};

function messageId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random()}`;
}

export const useConversationStore = create<ConversationStore>()(
  persist(
    (set) => ({
      languageCode: "kn",
      stateCode: "KA",
      draft: "",
      messages: [],
      lastTurn: null,
      setLanguageCode: (languageCode) => set({ languageCode }),
      setStateCode: (stateCode) => set({ stateCode }),
      setDraft: (draft) => set({ draft }),
      appendTurn: (callerText, response) =>
        set((state) => ({
          messages: [
            ...state.messages,
            { id: messageId(), role: "caller", text: callerText },
            { id: messageId(), role: "agent", text: response.response_text },
          ],
          lastTurn: response,
          draft: "",
        })),
      clearConversation: () => set({ messages: [], lastTurn: null, draft: "" }),
    }),
    {
      name: "sahaayak-conversation",
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        languageCode: state.languageCode,
        stateCode: state.stateCode,
      }),
    },
  ),
);
