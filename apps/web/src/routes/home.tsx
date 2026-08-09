import { lazy, Suspense, useCallback, useEffect, useMemo, useState, type FormEvent } from "react";

import { m } from "motion/react";

import { PublicFooter, Topbar } from "@/components/app/topbar";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { CatalogControls } from "@/features/catalog/components/catalog-controls";
import { useCompareStore } from "@/features/benefits/compare-store";
import { ConversationPanel } from "@/features/conversation/components/conversation-panel";
import { useResetSessionMutation, useTextTurnMutation, useVoiceTurnMutation } from "@/features/conversation/queries";
import { useConversationStore } from "@/features/conversation/store";
import { useCreateBrowserSessionMutation } from "@/features/session/queries";
import { useGuestSessionStore } from "@/features/session/store";
import { useCatalogQuery, useHealthQuery } from "@/features/catalog/queries";
import { useStreamingVoice } from "@/hooks/use-streaming-voice";
import { useVoiceRecorder } from "@/hooks/use-voice-recorder";
import { useUi } from "@/features/i18n/ui-provider";
import { AppTour } from "@/features/onboarding/components/app-tour";
import { audioDataUrl, cn } from "@/lib/utils";
import { ApiError, toUserMessage } from "@/lib/api";
import { motionTokens } from "@/lib/motion";
import { saveOfflineDraft } from "@/pwa/offline-store";

const HomeResults = lazy(() => import("@/features/home/components/home-results"));

export function HomePage() {
  const { t } = useUi();
  const catalogQuery = useCatalogQuery();
  const healthQuery = useHealthQuery();
  const textMutation = useTextTurnMutation();
  const voiceMutation = useVoiceTurnMutation();
  const resetMutation = useResetSessionMutation();
  const {
    mutate: createSession,
    isPending: sessionPending,
    error: sessionError,
  } = useCreateBrowserSessionMutation();

  const sessionId = useGuestSessionStore((state) => state.sessionId);
  const accessToken = useGuestSessionStore((state) => state.accessToken);
  const setSession = useGuestSessionStore((state) => state.setSession);
  const clearSession = useGuestSessionStore((state) => state.clearSession);
  const languageCode = useConversationStore((state) => state.languageCode);
  const stateCode = useConversationStore((state) => state.stateCode);
  const draft = useConversationStore((state) => state.draft);
  const messages = useConversationStore((state) => state.messages);
  const lastTurn = useConversationStore((state) => state.lastTurn);
  const setLanguageCode = useConversationStore((state) => state.setLanguageCode);
  const setStateCode = useConversationStore((state) => state.setStateCode);
  const setDraft = useConversationStore((state) => state.setDraft);
  const appendTurn = useConversationStore((state) => state.appendTurn);
  const clearConversation = useConversationStore((state) => state.clearConversation);
  const clearComparison = useCompareStore((state) => state.clear);

  const [feedback, setFeedback] = useState<{ kind: "error" | "notice"; text: string } | null>(null);

  const activeLanguages = useMemo(
    () => catalogQuery.data?.languages.filter((language) => language.is_active) ?? [],
    [catalogQuery.data?.languages],
  );
  const activeStates = useMemo(
    () => catalogQuery.data?.states.filter((state) => state.is_active) ?? [],
    [catalogQuery.data?.states],
  );
  const selectedLanguage = activeLanguages.find((language) => language.code === languageCode);
  const selectedState = activeStates.find((state) => state.code === stateCode);
  const stateCoverage =
    (catalogQuery.data?.coverage.by_state[stateCode] ?? 0) + (catalogQuery.data?.coverage.by_state.central ?? 0);
  const voiceInputAvailable = healthQuery.data?.speech_to_text ?? false;
  const baseSending = textMutation.isPending || voiceMutation.isPending;
  const handleStreamingTurn = useCallback(
    (response: Parameters<typeof appendTurn>[1]) => {
      appendTurn(response.transcript || "Voice turn", response);
    },
    [appendTurn],
  );
  const streamingVoice = useStreamingVoice({
    accessToken,
    languageCode,
    stateCode,
    enabled: Boolean(accessToken && languageCode && stateCode && voiceInputAvailable),
    onTurn: handleStreamingTurn,
  });
  const isSending = baseSending || streamingVoice.isBusy;
  const catalogLoading = catalogQuery.isPending;
  const disabled = isSending || sessionPending || !languageCode || !stateCode;
  const voiceDisabled = catalogLoading || baseSending || sessionPending || !accessToken || !languageCode || !stateCode;
  const audioSource = audioDataUrl(lastTurn?.audio_base64, lastTurn?.audio_mime_type);

  const handleVoiceComplete = useCallback(
    async (audio: Blob) => {
      if (baseSending || streamingVoice.isBusy || !languageCode || !stateCode) return;
      setFeedback(null);
      try {
        const response = await voiceMutation.mutateAsync({ audio, accessToken, languageCode, stateCode });
        appendTurn(response.transcript || "Voice turn", response);
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) clearSession();
        setFeedback({ kind: "error", text: toUserMessage(error) });
      }
    },
    [accessToken, appendTurn, baseSending, clearSession, languageCode, stateCode, streamingVoice.isBusy, voiceMutation],
  );
  const recorder = useVoiceRecorder(handleVoiceComplete);

  useEffect(() => {
    if (accessToken || sessionPending || !languageCode || !stateCode) return;
    createSession(
      { language_code: languageCode, state_code: stateCode },
      {
        onSuccess: (session) => {
          setSession(session);
          setLanguageCode(session.language_code);
          setStateCode(session.state_code);
        },
        onError: (error) => setFeedback({ kind: "error", text: toUserMessage(error) }),
      },
    );
  }, [accessToken, createSession, languageCode, sessionPending, setLanguageCode, setSession, setStateCode, stateCode]);

  useEffect(() => {
    if (activeLanguages.length > 0 && !activeLanguages.some((language) => language.code === languageCode)) {
      setLanguageCode(activeLanguages[0].code);
    }
  }, [activeLanguages, languageCode, setLanguageCode]);

  useEffect(() => {
    if (activeStates.length > 0 && !activeStates.some((state) => state.code === stateCode)) {
      setStateCode(activeStates[0].code);
    }
  }, [activeStates, setStateCode, stateCode]);

  useEffect(() => {
    const queryError = catalogQuery.error ?? healthQuery.error ?? sessionError;
    if (queryError && !feedback) {
      setFeedback({ kind: "error", text: toUserMessage(queryError) });
    }
  }, [catalogQuery.error, feedback, healthQuery.error, sessionError]);

  const handleTextSubmit = useCallback(
    async (event?: FormEvent<HTMLFormElement>) => {
      event?.preventDefault();
      const text = draft.trim();
      if (!text || disabled) return;

      setFeedback(null);
      if (!accessToken) {
        setFeedback({ kind: "notice", text: "There is no live connection yet. Save the question as a text draft, then send it when connected." });
        return;
      }
      setDraft("");
      try {
        const response = await textMutation.mutateAsync({
          payload: {
            text,
            language_code: languageCode,
            state_code: stateCode,
          },
          accessToken,
        });
        appendTurn(text, response);
      } catch (error) {
        setDraft(text);
        if (error instanceof ApiError && error.status === 401) clearSession();
        setFeedback({ kind: "error", text: toUserMessage(error) });
      }
    },
    [accessToken, appendTurn, clearSession, disabled, draft, languageCode, setDraft, stateCode, textMutation],
  );

  const handleSaveDraft = useCallback(async () => {
    const text = draft.trim();
    if (!text) return;
    try {
      await saveOfflineDraft(text, languageCode);
      setFeedback({ kind: "notice", text: "Saved as a text-only draft on this device. It expires after 24 hours." });
    } catch (error) {
      setFeedback({ kind: "error", text: error instanceof Error ? error.message : "Could not save the offline draft." });
    }
  }, [draft, languageCode]);

  const startRecording = useCallback(() => {
    setFeedback(null);
    if (streamingVoice.supported) {
      void streamingVoice.start();
      return;
    }
    recorder.startRecording();
  }, [recorder.startRecording, streamingVoice.start, streamingVoice.supported]);

  const stopRecording = useCallback(() => {
    if (streamingVoice.supported) {
      streamingVoice.stop();
      return;
    }
    recorder.stopRecording();
  }, [recorder.stopRecording, streamingVoice.stop, streamingVoice.supported]);

  const handleReset = useCallback(async () => {
    if (isSending || resetMutation.isPending) return;
    setFeedback(null);
    let remoteResetFailed = false;
    try {
      if (sessionId && accessToken) {
        await resetMutation.mutateAsync({ sessionId, accessToken });
      }
    } catch (error) {
      remoteResetFailed = true;
      // The user asked to clear the conversation. Do not leave the visible
      // transcript in place just because an old server-side child record
      // temporarily blocked deletion; the notice tells them exactly what was
      // and was not confirmed.
      console.warn("server_session_reset_failed", error);
    } finally {
      clearConversation();
      clearComparison();
      clearSession();
      setFeedback({
        kind: remoteResetFailed ? "error" : "notice",
        text: remoteResetFailed ? t("sessionClearedLocally") : t("sessionCleared"),
      });
    }
  }, [accessToken, clearComparison, clearConversation, clearSession, isSending, resetMutation, sessionId, t]);

  const connected = healthQuery.data?.status === "ok" && Boolean(accessToken);

  const [showDeferredResults, setShowDeferredResults] = useState(Boolean(lastTurn));

  useEffect(() => {
    if (lastTurn) {
      setShowDeferredResults(true);
      return;
    }
    if (showDeferredResults) return;
    const timer = window.setTimeout(() => setShowDeferredResults(true), 1200);
    return () => window.clearTimeout(timer);
  }, [lastTurn, showDeferredResults]);

  return (
    <div className="min-h-svh bg-background text-foreground">
      <Topbar
        sessionId={sessionId}
        connected={connected}
        currentLanguage={selectedLanguage?.native_name ?? selectedLanguage?.name}
        activeSection="home"
      />

      <main id="main-content" tabIndex={-1} className="outline-none" aria-labelledby="page-title">
        <section className="mx-auto grid max-w-[1200px] gap-8 px-4 py-10 sm:px-6 sm:py-14 lg:grid-cols-[minmax(260px,.72fr)_minmax(520px,1.28fr)] lg:px-8 lg:py-16">
          <m.header
            className="self-start lg:sticky lg:top-8"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: motionTokens.slow, ease: motionTokens.ease }}
          >
            <p className="text-sm font-semibold text-primary">{t("heroKicker")}</p>
            <h1 id="page-title" className="mt-4 max-w-xl text-3xl font-bold leading-tight tracking-tight text-foreground sm:text-4xl">
              {t("heroTitle")}
            </h1>
            <p className="mt-5 max-w-xl text-base leading-7 text-muted-foreground">
              {t("heroDescription")}
            </p>

            <Card className="mt-8 max-w-xl border-primary/25 bg-secondary/50">
              <CardContent className="p-5">
                <p className="text-sm font-semibold text-secondary-foreground">{t("benefitsLoaded")}</p>
                <p className="mt-2 text-3xl font-bold text-primary">{catalogQuery.data?.coverage.total ?? "—"}</p>
                <p className="mt-3 text-sm leading-6 text-muted-foreground">
                  {t("schemes")} · {t("scholarships")} · {t("jobDiscovery")}
                </p>
              </CardContent>
            </Card>
          </m.header>

          <m.section
            id="conversation"
            aria-labelledby="conversation-title"
            tabIndex={-1}
            className="scroll-mt-8 space-y-4 outline-none"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: motionTokens.slow, delay: 0.05, ease: motionTokens.ease }}
          >
            <CatalogControls
              languages={activeLanguages}
              states={activeStates}
              languageCode={languageCode}
              stateCode={stateCode}
              stateName={selectedState?.name}
              stateCoverage={stateCoverage}
              disabled={catalogLoading || isSending}
              onLanguageChange={setLanguageCode}
              onStateChange={setStateCode}
            />
            <ConversationPanel
              messages={messages}
              draft={draft}
              selectedLanguageName={selectedLanguage?.name}
              audioSource={audioSource}
              isSending={isSending}
              isResetting={resetMutation.isPending}
              disabled={disabled}
              voiceDisabled={voiceDisabled}
              recording={streamingVoice.supported ? streamingVoice.isListening : recorder.isRecording}
              voiceInputAvailable={voiceInputAvailable}
              textToSpeechAvailable={healthQuery.data?.text_to_speech ?? false}
              recorderError={streamingVoice.supported ? streamingVoice.error : recorder.error}
              transcriptDraft={streamingVoice.transcriptDraft}
              onDraftChange={setDraft}
              onSaveDraft={() => void handleSaveDraft()}
              onTranscriptChange={streamingVoice.updateTranscript}
              onSubmitTranscript={streamingVoice.submitTranscript}
              onCancelTranscript={streamingVoice.cancelTranscript}
              onSubmit={(event) => void handleTextSubmit(event)}
              onSuggestion={setDraft}
              onStartRecording={startRecording}
              onStopRecording={stopRecording}
              onReset={() => void handleReset()}
            />

            <div
              className="min-h-6 px-1 text-sm"
              role={feedback?.kind === "error" ? "alert" : "status"}
              aria-live={feedback?.kind === "error" ? "assertive" : "polite"}
            >
              {feedback && (
                <p className={cn("leading-5", feedback.kind === "error" ? "text-destructive" : "text-success")}>
                  {feedback.text}
                </p>
              )}
              {!feedback && catalogLoading && <p className="text-muted-foreground">{t("loadingCatalog")}</p>}
            </div>

            {lastTurn && (
              <Card id="result-notice" className="scroll-mt-8 border-primary/35 bg-secondary/60 shadow-sm">
                <CardContent className="flex flex-col gap-4 p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5">
                  <div>
                    <p className="text-sm font-bold text-secondary-foreground">
                      {lastTurn.pending_slot ? t("resultNeedsMoreInfo") : t("resultReadyTitle")}
                    </p>
                    <p className="mt-1 text-sm leading-6 text-muted-foreground">
                      {lastTurn.pending_slot
                        ? t("resultNeedsMoreInfoDescription")
                        : t("resultReadyDescription", {count: lastTurn.matches.length})}
                    </p>
                  </div>
                  <Button asChild size="sm" className="shrink-0">
                    <a href="#results">{t("reviewResults")}</a>
                  </Button>
                </CardContent>
              </Card>
            )}
          </m.section>
        </section>

        {showDeferredResults ? (
          <Suspense
            fallback={
                <section
                  id="results"
                  data-tour="results"
                  className="mx-auto min-h-24 max-w-[1200px] px-4 pb-14 sm:px-6 lg:px-8"
                  aria-busy="true"
                >
                <p className="text-sm text-muted-foreground" role="status">Loading your saved work…</p>
              </section>
            }
          >
            {sessionId && accessToken ? (
              <HomeResults
                lastTurn={lastTurn}
                sessionId={sessionId}
                accessToken={accessToken}
                languageCode={languageCode}
                onError={(text) => setFeedback({ kind: "error", text })}
              />
            ) : null}
          </Suspense>
        ) : (
          <section
            id="results"
            data-tour="results"
            className="mx-auto min-h-24 max-w-[1200px] px-4 pb-14 sm:px-6 lg:px-8"
            aria-busy="true"
          />
        )}
      </main>

      <AppTour />
      <PublicFooter />
    </div>
  );
}
