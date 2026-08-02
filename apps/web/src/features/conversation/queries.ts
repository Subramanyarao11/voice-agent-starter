import { useMutation } from "@tanstack/react-query";

import { resetSession, sendTextTurn, sendVoiceTurn, type TurnRequest } from "@/lib/api";

export function useTextTurnMutation() {
  return useMutation({ mutationFn: (payload: TurnRequest) => sendTextTurn(payload) });
}

export function useVoiceTurnMutation() {
  return useMutation({
    mutationFn: ({
      audio,
      callerId,
      languageCode,
      stateCode,
    }: {
      audio: Blob;
      callerId: string;
      languageCode: string;
      stateCode: string;
    }) =>
      sendVoiceTurn(audio, {
        caller_id: callerId,
        language_code: languageCode,
        state_code: stateCode,
        speak: true,
      }),
  });
}

export function useResetSessionMutation() {
  return useMutation({ mutationFn: (callerId: string) => resetSession(callerId) });
}
