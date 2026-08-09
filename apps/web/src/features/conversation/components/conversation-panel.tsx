import type { FormEvent } from "react";

import { RotateCcw } from "lucide-react";

import type { ConversationMessage } from "@/features/conversation/store";
import { useAudioReply } from "@/hooks/use-audio-reply";
import { Button } from "@/components/ui/button";
import { Composer } from "@/features/conversation/components/composer";
import { MessageList } from "@/features/conversation/components/message-list";
import { TranscriptEditor } from "@/features/conversation/components/transcript-editor";
import { useUi } from "@/features/i18n/ui-provider";

type ConversationPanelProps = {
  messages: ConversationMessage[];
  draft: string;
  selectedLanguageName?: string;
  audioSource: string | null;
  isSending: boolean;
  isResetting: boolean;
  disabled: boolean;
  voiceDisabled: boolean;
  recording: boolean;
  voiceInputAvailable: boolean;
  textToSpeechAvailable: boolean;
  recorderError: string | null;
  transcriptDraft: string | null;
  onDraftChange: (draft: string) => void;
  onSaveDraft: () => void;
  onTranscriptChange: (transcript: string) => void;
  onSubmitTranscript: (transcript: string) => void;
  onCancelTranscript: () => void;
  onSubmit: (event?: FormEvent<HTMLFormElement>) => void;
  onSuggestion: (suggestion: string) => void;
  onStartRecording: () => void;
  onStopRecording: () => void;
  onReset: () => void;
};

function AudioReply({ source }: { source: string | null }) {
  const { t } = useUi();
  const { audioRef, autoplayBlocked } = useAudioReply(source);

  if (!source) return null;

  return (
    <section
      className="flex flex-wrap items-center gap-3 border-t border-border px-5 py-4 sm:px-8"
      aria-label={t("audioAnswer")}
    >
      <span className="text-sm font-semibold text-muted-foreground">{t("latestAnswer")}</span>
      <audio
        ref={audioRef}
        controls
        src={source}
        className="h-10 min-w-56 flex-1 accent-primary"
        aria-label={t("playLatestAnswer")}
      >
        {t("browserCannotPlay")}
      </audio>
      {autoplayBlocked && (
          <span className="text-sm text-muted-foreground" role="status">
          {t("pressPlay")}
        </span>
      )}
    </section>
  );
}

export function ConversationPanel({
  messages,
  draft,
  selectedLanguageName,
  audioSource,
  isSending,
  isResetting,
  disabled,
  voiceDisabled,
  recording,
  voiceInputAvailable,
  textToSpeechAvailable,
  recorderError,
  transcriptDraft,
  onDraftChange,
  onSaveDraft,
  onTranscriptChange,
  onSubmitTranscript,
  onCancelTranscript,
  onSubmit,
  onSuggestion,
  onStartRecording,
  onStopRecording,
  onReset,
}: ConversationPanelProps) {
  const { t } = useUi();
  return (
    <div data-tour="conversation" className="overflow-hidden rounded-lg border border-border bg-card shadow-sm">
      <div className="flex items-start justify-between gap-4 px-5 pb-3 pt-6 sm:px-8">
        <div>
          <span className="text-sm font-semibold text-primary">{t("yourConversation")}</span>
          <h2 id="conversation-title" className="mt-2 text-xl font-bold tracking-tight text-foreground sm:text-2xl">
            {t("conversationTitle")}
          </h2>
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="-mr-2 mt-[-0.35rem] text-muted-foreground hover:bg-secondary hover:text-foreground"
          onClick={onReset}
          disabled={isResetting || isSending}
        >
          <RotateCcw className={`size-3.5 ${isResetting ? "motion-safe:animate-spin motion-reduce:animate-none" : ""}`} />
          <span className="hidden sm:inline">{isResetting ? t("clearing") : t("resetSession")}</span>
        </Button>
      </div>

      <MessageList
        messages={messages}
        isSending={isSending && transcriptDraft === null}
        onSuggestion={onSuggestion}
      />
      {transcriptDraft !== null && (
        <TranscriptEditor
          value={transcriptDraft}
          onChange={onTranscriptChange}
          onSubmit={() => onSubmitTranscript(transcriptDraft)}
          onCancel={onCancelTranscript}
        />
      )}
      <AudioReply source={audioSource} />
      <Composer
        draft={draft}
        selectedLanguageName={selectedLanguageName}
        isSending={isSending}
        disabled={disabled}
        voiceDisabled={voiceDisabled}
        recording={recording}
        voiceInputAvailable={voiceInputAvailable}
        textToSpeechAvailable={textToSpeechAvailable}
        recorderError={recorderError}
        onDraftChange={onDraftChange}
        onSubmit={onSubmit}
        onStartRecording={onStartRecording}
        onStopRecording={onStopRecording}
      />
      {draft.trim() && (
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border bg-muted/30 px-5 py-3 sm:px-8">
          <p className="text-sm leading-5 text-muted-foreground">
            Save this text question on this device for up to 24 hours if the connection is unreliable.
          </p>
          <Button type="button" variant="outline" size="sm" onClick={onSaveDraft} disabled={isSending}>
            Save text draft
          </Button>
        </div>
      )}
    </div>
  );
}
