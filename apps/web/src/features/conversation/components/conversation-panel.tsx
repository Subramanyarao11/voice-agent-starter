import type { FormEvent } from "react";

import { RotateCcw } from "lucide-react";

import type { ConversationMessage } from "@/features/conversation/store";
import { useAudioReply } from "@/hooks/use-audio-reply";
import { Button } from "@/components/ui/button";
import { Composer } from "@/features/conversation/components/composer";
import { MessageList } from "@/features/conversation/components/message-list";
import { TranscriptEditor } from "@/features/conversation/components/transcript-editor";

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
  const { audioRef, autoplayBlocked } = useAudioReply(source);

  if (!source) return null;

  return (
    <section
      className="flex flex-wrap items-center gap-3 border-t border-paper/10 px-5 py-3 sm:px-8"
      aria-label="Audio answer"
    >
      <span className="font-mono text-[0.6rem] uppercase tracking-[0.18em] text-paper/40">Last answer</span>
      <audio
        ref={audioRef}
        controls
        src={source}
        className="h-8 min-w-56 flex-1 accent-acid"
        aria-label="Play the latest Sahaayak answer"
      >
        Your browser cannot play this answer.
      </audio>
      {autoplayBlocked && (
        <span className="text-[0.68rem] text-paper/40" role="status">
          Press play to hear it.
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
  onTranscriptChange,
  onSubmitTranscript,
  onCancelTranscript,
  onSubmit,
  onSuggestion,
  onStartRecording,
  onStopRecording,
  onReset,
}: ConversationPanelProps) {
  return (
    <div className="overflow-hidden rounded-3xl border border-paper/15 bg-ink-soft/90 shadow-2xl shadow-black/20 backdrop-blur-sm">
      <div className="flex items-start justify-between gap-4 px-5 pb-3 pt-6 sm:px-8">
        <div>
          <span className="font-mono text-[0.62rem] uppercase tracking-[0.2em] text-acid/80">Your conversation</span>
          <h2 id="conversation-title" className="mt-2 text-xl font-extrabold tracking-tight text-paper sm:text-2xl">
            Tell me what you’re looking for.
          </h2>
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="-mr-2 mt-[-0.35rem] text-paper/45 hover:bg-paper/10 hover:text-paper"
          onClick={onReset}
          disabled={isResetting || isSending}
        >
          <RotateCcw className={`size-3.5 ${isResetting ? "animate-spin" : ""}`} />
          <span className="hidden sm:inline">{isResetting ? "Clearing…" : "Reset session"}</span>
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
    </div>
  );
}
