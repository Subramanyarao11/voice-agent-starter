import { useEffect, useRef } from "react";

import { Check, PencilLine, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { useUi } from "@/features/i18n/ui-provider";

type TranscriptEditorProps = {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onCancel: () => void;
};

/** Keeps speech recognition human-approved before it reaches the reasoning graph. */
export function TranscriptEditor({ value, onChange, onSubmit, onCancel }: TranscriptEditorProps) {
  const { t } = useUi();
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
    inputRef.current?.select();
  }, []);

  return (
    <Card className="mx-5 mb-4 border-primary/25 bg-secondary/50 text-foreground sm:mx-8">
      <CardContent className="space-y-3 p-4 sm:p-5">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-full bg-secondary text-primary" aria-hidden="true">
            <PencilLine className="size-4" />
          </span>
          <div>
            <h3 className="text-sm font-bold">{t("reviewHeard")}</h3>
            <p className="mt-1 text-xs leading-5 text-muted-foreground">
              {t("reviewHeardDescription")}
            </p>
          </div>
        </div>

        <form
          onSubmit={(event) => {
            event.preventDefault();
            if (value.trim()) onSubmit();
          }}
        >
          <label htmlFor="voice-transcript-editor" className="sr-only">
            {t("editVoiceTranscript")}
          </label>
          <Textarea
            ref={inputRef}
            id="voice-transcript-editor"
            value={value}
            maxLength={2_000}
            rows={3}
            onChange={(event) => onChange(event.target.value)}
            aria-describedby="voice-transcript-help"
            className="border-border bg-background text-foreground placeholder:text-muted-foreground focus-visible:border-primary"
          />
          <div id="voice-transcript-help" className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
            <span>{t("transcriptNotSent")}</span>
            <span aria-live="polite">{value.length}/2,000</span>
          </div>
          <div className="mt-4 flex flex-wrap justify-end gap-2">
          <Button type="button" variant="ghost" size="sm" className="text-muted-foreground hover:bg-secondary hover:text-foreground" onClick={onCancel}>
              <X className="size-3.5" aria-hidden="true" />
              {t("cancel")}
            </Button>
          <Button type="submit" size="sm" disabled={!value.trim()}>
              <Check className="size-3.5" aria-hidden="true" />
              {t("useTranscript")}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
