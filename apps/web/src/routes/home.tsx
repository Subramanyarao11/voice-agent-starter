import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";

import { motion } from "motion/react";

import { Topbar } from "@/components/app/topbar";
import { ComparisonPanel } from "@/features/benefits/components/comparison-panel";
import { useCompareStore } from "@/features/benefits/compare-store";
import { CatalogControls } from "@/features/catalog/components/catalog-controls";
import { ConversationPanel } from "@/features/conversation/components/conversation-panel";
import { MatchesPanel } from "@/features/conversation/components/matches-panel";
import { SourcesPanel } from "@/features/conversation/components/sources-panel";
import { TurnInspector } from "@/features/conversation/components/turn-inspector";
import { useResetSessionMutation, useTextTurnMutation, useVoiceTurnMutation } from "@/features/conversation/queries";
import { useConversationStore } from "@/features/conversation/store";
import { useCreateBrowserSessionMutation } from "@/features/session/queries";
import { useGuestSessionStore } from "@/features/session/store";
import { useCatalogQuery, useHealthQuery } from "@/features/catalog/queries";
import {
  useRemoveSavedBenefitMutation,
  useSaveBenefitMutation,
  useSavedBenefitsQuery,
} from "@/features/saved/queries";
import { ContactSettingsPanel } from "@/features/contacts/components/contact-settings-panel";
import { SavedBenefitsPanel } from "@/features/saved/components/saved-benefits-panel";
import { useStreamingVoice } from "@/hooks/use-streaming-voice";
import { useVoiceRecorder } from "@/hooks/use-voice-recorder";
import { audioDataUrl, cn } from "@/lib/utils";
import { ApiError, toUserMessage } from "@/lib/api";

export function HomePage() {
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
  const savedBenefitsQuery = useSavedBenefitsQuery(sessionId, accessToken);
  const saveBenefitMutation = useSaveBenefitMutation(sessionId, accessToken);
  const removeSavedBenefitMutation = useRemoveSavedBenefitMutation(sessionId, accessToken);
  const comparedBenefitIds = useCompareStore((state) => state.benefitIds);
  const toggleCompare = useCompareStore((state) => state.toggle);

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
  const disabled = catalogLoading || isSending || sessionPending || !accessToken || !languageCode || !stateCode;
  const voiceDisabled = catalogLoading || baseSending || sessionPending || !accessToken || !languageCode || !stateCode;
  const audioSource = audioDataUrl(lastTurn?.audio_base64, lastTurn?.audio_mime_type);
  const savedBenefitIds = useMemo(
    () => new Set(savedBenefitsQuery.data?.map((benefit) => benefit.benefit_id) ?? []),
    [savedBenefitsQuery.data],
  );

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
    try {
      await resetMutation.mutateAsync({ sessionId, accessToken });
      clearConversation();
      clearSession();
      setFeedback({ kind: "notice", text: "Session cleared. Your next turn starts a fresh conversation." });
    } catch (error) {
      setFeedback({ kind: "error", text: toUserMessage(error) });
    }
  }, [accessToken, clearConversation, clearSession, isSending, resetMutation, sessionId]);

  const handleToggleSaved = useCallback(
    (benefitId: string, saved: boolean) => {
      const mutation = saved ? removeSavedBenefitMutation : saveBenefitMutation;
      mutation.mutate(benefitId, {
        onError: (error) => setFeedback({ kind: "error", text: toUserMessage(error) }),
      });
    },
    [removeSavedBenefitMutation, saveBenefitMutation],
  );

  const connected = healthQuery.data?.status === "ok" && Boolean(accessToken);

  return (
    <main
      className="relative min-h-svh overflow-hidden bg-ink px-4 py-5 text-paper sm:px-8 lg:px-12"
      aria-labelledby="page-title"
    >
      <div className="pointer-events-none absolute -left-40 top-16 size-[30rem] rounded-full bg-blue/10 blur-3xl" />
      <div className="pointer-events-none absolute -right-48 top-[28rem] size-[36rem] rounded-full bg-orange/10 blur-3xl" />

      <a
        href="#conversation"
        onClick={(event) => {
          event.preventDefault();
          const target = document.getElementById("conversation");
          target?.focus();
          target?.scrollIntoView({ behavior: "smooth", block: "start" });
        }}
        className="sr-only fixed left-4 top-4 z-50 rounded-lg bg-acid px-4 py-2 font-semibold text-ink focus:not-sr-only focus:outline-none focus:ring-2 focus:ring-paper"
      >
        Skip to conversation
      </a>

      <Topbar sessionId={sessionId} connected={connected} />

      <section className="relative mx-auto grid max-w-[1440px] gap-12 py-16 lg:grid-cols-[minmax(260px,.72fr)_minmax(520px,1.28fr)] lg:gap-24 lg:py-28">
        <motion.div
          className="self-start lg:sticky lg:top-12"
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, ease: "easeOut" }}
        >
          <p className="font-mono text-[0.62rem] uppercase tracking-[0.24em] text-acid">A calmer way to find out</p>
          <h1 id="page-title" className="mt-5 max-w-xl text-5xl font-extrabold leading-[0.98] tracking-[-0.055em] text-paper sm:text-7xl">
            Find the help
            <br />
            meant for <em className="font-serif font-normal text-acid">you.</em>
          </h1>
          <p className="mt-7 max-w-md text-base leading-7 text-paper/60 sm:text-lg">
            Speak or type what you need. Sahaayak asks only the questions that change your answer, then explains what it found.
          </p>

          <div className="mt-10 flex items-center gap-4">
            <span className="grid size-11 place-items-center rounded-xl border border-acid/30 bg-acid/10 text-xl text-acid">↗</span>
            <span className="grid gap-1">
              <strong className="font-mono text-2xl font-medium text-paper">{catalogQuery.data?.coverage.total ?? "—"}</strong>
              <span className="text-xs text-paper/45">benefits loaded for this demo</span>
            </span>
          </div>

          <div className="mt-12 flex flex-wrap gap-x-6 gap-y-3 font-mono text-[0.65rem] uppercase tracking-[0.14em] text-paper/40">
            <span><b className="mr-2 text-acid">01</b>schemes</span>
            <span><b className="mr-2 text-acid">02</b>scholarships</span>
            <span><b className="mr-2 text-acid">03</b>job discovery</span>
          </div>
        </motion.div>

        <motion.section
          id="conversation"
          aria-labelledby="conversation-title"
          tabIndex={-1}
          className="relative scroll-mt-8 space-y-4 outline-none"
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, delay: 0.1, ease: "easeOut" }}
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
            onDraftChange={setDraft}
            onSubmit={(event) => void handleTextSubmit(event)}
            onSuggestion={setDraft}
            onStartRecording={startRecording}
            onStopRecording={stopRecording}
            onReset={() => void handleReset()}
          />

          <div
            className="min-h-6 px-1 text-xs"
            role={feedback?.kind === "error" ? "alert" : "status"}
            aria-live={feedback?.kind === "error" ? "assertive" : "polite"}
          >
            {feedback && (
              <p className={cn("leading-5", feedback.kind === "error" ? "text-orange" : "text-acid")}>
                {feedback.text}
              </p>
            )}
            {!feedback && catalogLoading && <p className="text-paper/40">Loading language and state catalog…</p>}
          </div>
        </motion.section>
      </section>

      <div className="relative mx-auto max-w-[1440px] space-y-10 pb-14">
        <TurnInspector turn={lastTurn} />
        <SourcesPanel turn={lastTurn} />
        <MatchesPanel
          turn={lastTurn}
          savedBenefitIds={savedBenefitIds}
          onToggleSaved={handleToggleSaved}
          comparedBenefitIds={new Set(comparedBenefitIds)}
          onToggleCompare={(benefitId, compared) => {
            if (compared || comparedBenefitIds.length < 3) toggleCompare(benefitId);
          }}
        />
        <ComparisonPanel />
        <SavedBenefitsPanel
          sessionId={sessionId}
          accessToken={accessToken}
          savedBenefits={savedBenefitsQuery.data ?? []}
        />
        {accessToken ? (
          <ContactSettingsPanel
            sessionId={sessionId}
            accessToken={accessToken}
            languageCode={languageCode}
          />
        ) : null}
      </div>

      <footer className="relative mx-auto flex max-w-[1440px] flex-wrap justify-between gap-3 border-t border-paper/10 py-6 text-[0.68rem] uppercase tracking-[0.12em] text-paper/35">
        <span>Built for a real conversation, not a nationwide coverage claim.</span>
        <span>Kannada · Hindi · English</span>
      </footer>
    </main>
  );
}
