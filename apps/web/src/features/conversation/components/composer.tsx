import type { FormEvent, KeyboardEvent } from "react";

import { ArrowUpRight, LoaderCircle, Mic, Square, Volume2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useUi } from "@/features/i18n/ui-provider";

type ComposerProps = {
  draft: string;
  selectedLanguageName?: string;
  isSending: boolean;
  disabled: boolean;
  voiceDisabled: boolean;
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
  voiceDisabled,
  recording,
  voiceInputAvailable,
  textToSpeechAvailable,
  recorderError,
  onDraftChange,
  onSubmit,
  onStartRecording,
  onStopRecording,
}: ComposerProps) {
  const { t } = useUi();
  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      onSubmit();
    }
  }

  return (
    <form
      className="border-t border-border px-5 pb-4 pt-5 sm:px-8"
      onSubmit={(event) => onSubmit(event)}
      aria-label={t("sendMessage")}
    >
      <label htmlFor="message-input" className="sr-only">
        {t("messageForSahaayak")}
      </label>
      <Textarea
        id="message-input"
        value={draft}
        onChange={(event) => onDraftChange(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={selectedLanguageName ? t("typeInLanguage", {language: selectedLanguageName}) : t("typeWhatYouNeed")}
        rows={2}
        disabled={disabled || recording}
        aria-describedby="composer-help"
        className="border-border bg-background px-4 py-3 text-base leading-6 focus-visible:border-primary focus-visible:bg-background"
      />

      <div className="mt-3 flex items-center justify-between gap-3">
        <Button
          type="button"
          variant="outline"
          size="sm"
          className={recording ? "border-destructive/50 bg-destructive/10 text-destructive" : "border-border text-foreground"}
          onClick={recording ? onStopRecording : onStartRecording}
          disabled={voiceDisabled || !voiceInputAvailable}
          aria-label={voiceInputAvailable ? (recording ? t("stopRecording") : t("recordVoice")) : t("speechToTextUnavailable")}
          aria-pressed={recording}
          title={voiceInputAvailable ? (recording ? t("stopRecording") : t("recordVoice")) : t("speechToTextUnavailable")}
        >
          {recording ? <Square className="size-3.5 fill-current" /> : <Mic className="size-3.5" />}
          <span>{recording ? t("stop") : t("speak")}</span>
        </Button>

        <Button
          type="submit"
          size="sm"
          className="bg-primary px-4 text-primary-foreground hover:bg-primary/90"
          disabled={disabled || recording || !draft.trim()}
          aria-label={t("sendMessage")}
        >
          {isSending ? <LoaderCircle className="size-3.5 motion-safe:animate-spin motion-reduce:animate-none" /> : <span>{t("sendMessage")}</span>}
          <ArrowUpRight className="size-4" />
        </Button>
      </div>

      <p
        id="composer-help"
        className="mt-3 flex min-h-5 items-center gap-1.5 text-sm leading-5 text-muted-foreground"
        role={recorderError ? "alert" : "status"}
        aria-live={recorderError ? "assertive" : "polite"}
      >
        {recording ? (
          <>{t("listening")}</>
        ) : recorderError ? (
          <span className="text-destructive">{recorderError}</span>
        ) : textToSpeechAvailable ? (
          <><Volume2 className="size-3" aria-hidden="true" /> {t("voiceReplies")} {t("keyboardHint")}</>
        ) : (
          <>{t("textReplies")} {t("keyboardHint")}</>
        )}
      </p>
    </form>
  );
}
