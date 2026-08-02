import { useMutation } from "@tanstack/react-query";

import { resetSession, sendTextTurn, sendVoiceTurn, type TurnRequest } from "@/lib/api";

export function useTextTurnMutation() {
  return useMutation({
    mutationFn: ({ payload, accessToken }: { payload: TurnRequest; accessToken: string }) =>
      sendTextTurn(payload, accessToken),
  });
}

export function useVoiceTurnMutation() {
  return useMutation({
    mutationFn: ({
      audio,
      languageCode,
      stateCode,
      accessToken,
    }: {
      audio: Blob;
      languageCode: string;
      stateCode: string;
      accessToken: string;
    }) =>
      sendVoiceTurn(audio, {
        language_code: languageCode,
        state_code: stateCode,
        speak: true,
      }, accessToken),
  });
}

export function useResetSessionMutation() {
  return useMutation({
    mutationFn: ({ sessionId, accessToken }: { sessionId: string; accessToken: string }) =>
      resetSession(sessionId, accessToken),
  });
}
