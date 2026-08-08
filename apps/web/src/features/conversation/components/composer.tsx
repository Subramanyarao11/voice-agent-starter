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
      className="border-t border-paper/10 px-5 pb-3 pt-4 sm:px-8"
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
        className="border-transparent bg-paper/[0.04] px-4 py-3 text-sm leading-6 focus-visible:border-acid/30 focus-visible:bg-paper/[0.06]"
      />

      <div className="mt-3 flex items-center justify-between gap-3">
        <Button
          type="button"
          variant="outline"
          size="sm"
          className={recording ? "border-orange/50 bg-orange/10 text-orange" : "border-paper/15 text-paper/65"}
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
          className="bg-acid px-4 text-ink hover:bg-acid/90"
          disabled={disabled || recording || !draft.trim()}
          aria-label={t("sendMessage")}
        >
          {isSending ? <LoaderCircle className="size-3.5 animate-spin" /> : <span>{t("sendMessage")}</span>}
          <ArrowUpRight className="size-4" />
        </Button>
      </div>

      <p
        id="composer-help"
        className="mt-3 flex min-h-5 items-center gap-1.5 text-[0.68rem] leading-5 text-paper/40"
        role={recorderError ? "alert" : "status"}
        aria-live={recorderError ? "assertive" : "polite"}
      >
        {recording ? (
          <>{t("listening")}</>
        ) : recorderError ? (
          <span className="text-orange">{recorderError}</span>
        ) : textToSpeechAvailable ? (
          <><Volume2 className="size-3" aria-hidden="true" /> {t("voiceReplies")} {t("keyboardHint")}</>
        ) : (
          <>{t("textReplies")} {t("keyboardHint")}</>
        )}
      </p>
    </form>
  );
}
