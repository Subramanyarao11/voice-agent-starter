import type { FormEvent, KeyboardEvent } from "react";

import { ArrowUpRight, LoaderCircle, Mic, Square, Volume2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

type ComposerProps = {
  draft: string;
  selectedLanguageName?: string;
  isSending: boolean;
  disabled: boolean;
  recording: boolean;
  voiceInputAvailable: boolean;
  textToSpeechAvailable: boolean;
  recorderError: string | null;
  onDraftChange: (draft: string) => void;
  onSubmit: (event?: FormEvent<HTMLFormElement>) => void;
  onStartRecording: () => void;
  onStopRecording: () => void;
};

export function Composer({
  draft,
  selectedLanguageName,
  isSending,
  disabled,
  recording,
  voiceInputAvailable,
  textToSpeechAvailable,
  recorderError,
  onDraftChange,
  onSubmit,
  onStartRecording,
  onStopRecording,
}: ComposerProps) {
  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      onSubmit();
    }
  }

  return (
    <form className="border-t border-paper/10 px-5 pb-3 pt-4 sm:px-8" onSubmit={(event) => onSubmit(event)}>
      <Textarea
        value={draft}
        onChange={(event) => onDraftChange(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={selectedLanguageName ? `Type in ${selectedLanguageName}, English, or a mix…` : "Type what you need…"}
        rows={2}
        disabled={disabled || recording}
        aria-label="Your message"
        className="border-transparent bg-paper/[0.04] px-4 py-3 text-sm leading-6 focus-visible:border-acid/30 focus-visible:bg-paper/[0.06]"
      />

      <div className="mt-3 flex items-center justify-between gap-3">
        <Button
          type="button"
          variant="outline"
          size="sm"
          className={recording ? "border-orange/50 bg-orange/10 text-orange" : "border-paper/15 text-paper/65"}
          onClick={recording ? onStopRecording : onStartRecording}
          disabled={disabled || !voiceInputAvailable}
          title={voiceInputAvailable ? (recording ? "Stop recording" : "Record a voice message") : "Speech-to-text is not configured"}
        >
          {recording ? <Square className="size-3.5 fill-current" /> : <Mic className="size-3.5" />}
          <span>{recording ? "Stop" : "Speak"}</span>
        </Button>

        <Button type="submit" size="sm" className="bg-acid px-4 text-ink hover:bg-acid/90" disabled={disabled || recording || !draft.trim()}>
          {isSending ? <LoaderCircle className="size-3.5 animate-spin" /> : <span>Send</span>}
          <ArrowUpRight className="size-4" />
        </Button>
      </div>

      <p className="mt-3 flex min-h-5 items-center gap-1.5 text-[0.68rem] leading-5 text-paper/40">
        {recording ? (
          <>Listening… press Stop when you’re done.</>
        ) : recorderError ? (
          <span className="text-orange">{recorderError}</span>
        ) : textToSpeechAvailable ? (
          <><Volume2 className="size-3" /> Voice replies are available for this API session.</>
        ) : (
          <>Text replies are ready. Voice output is off until the API has TTS keys.</>
        )}
      </p>
    </form>
  );
}
