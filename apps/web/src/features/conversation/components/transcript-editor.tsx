import { useEffect, useRef } from "react";

import { Check, PencilLine, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";

type TranscriptEditorProps = {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onCancel: () => void;
};

/** Keeps speech recognition human-approved before it reaches the reasoning graph. */
export function TranscriptEditor({ value, onChange, onSubmit, onCancel }: TranscriptEditorProps) {
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
    inputRef.current?.select();
  }, []);

  return (
    <Card className="mx-5 mb-4 border-acid/25 bg-acid/[0.06] text-paper sm:mx-8">
      <CardContent className="space-y-3 p-4 sm:p-5">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-full bg-acid/15 text-acid" aria-hidden="true">
            <PencilLine className="size-4" />
          </span>
          <div>
            <h3 className="text-sm font-bold">Review what I heard</h3>
            <p className="mt-1 text-xs leading-5 text-paper/60">
              Fix names, places, or numbers before Sahaayak uses this message.
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
            Edit the voice transcript
          </label>
          <Textarea
            ref={inputRef}
            id="voice-transcript-editor"
            value={value}
            maxLength={2_000}
            rows={3}
            onChange={(event) => onChange(event.target.value)}
            aria-describedby="voice-transcript-help"
            className="border-paper/15 bg-ink/40 text-paper placeholder:text-paper/35 focus-visible:border-acid/50"
          />
          <div id="voice-transcript-help" className="mt-2 flex flex-wrap items-center justify-between gap-2 text-[0.68rem] text-paper/45">
            <span>Nothing is sent until you choose “Use this”.</span>
            <span aria-live="polite">{value.length}/2,000</span>
          </div>
          <div className="mt-4 flex flex-wrap justify-end gap-2">
            <Button type="button" variant="ghost" size="sm" className="text-paper/65 hover:bg-paper/10 hover:text-paper" onClick={onCancel}>
              <X className="size-3.5" aria-hidden="true" />
              Cancel
            </Button>
            <Button type="submit" size="sm" className="bg-acid text-ink hover:bg-acid/90" disabled={!value.trim()}>
              <Check className="size-3.5" aria-hidden="true" />
              Use this transcript
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
