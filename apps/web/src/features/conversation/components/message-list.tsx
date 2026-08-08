import { AnimatePresence, m } from "motion/react";
import { MessageCircle } from "lucide-react";

import type { ConversationMessage } from "@/features/conversation/store";
import { Button } from "@/components/ui/button";
import { useUi } from "@/features/i18n/ui-provider";
import { motionTokens } from "@/lib/motion";

type MessageListProps = {
  messages: ConversationMessage[];
  isSending: boolean;
  onSuggestion: (suggestion: string) => void;
};

export function MessageList({ messages, isSending, onSuggestion }: MessageListProps) {
  const { t } = useUi();
  const suggestions = [t("scholarshipSuggestion"), t("schemeSuggestion")];
  return (
    <div
      className="min-h-72 space-y-5 px-5 py-6 sm:min-h-80 sm:px-8"
      role="log"
      aria-live="polite"
      aria-relevant="additions"
      aria-label={t("conversationMessages")}
    >
      {messages.length === 0 ? (
        <m.div
          className="flex min-h-60 flex-col items-center justify-center text-center"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: motionTokens.slow, ease: motionTokens.ease }}
        >
          <span className="mb-4 grid size-12 place-items-center rounded-lg border border-primary/30 bg-secondary text-primary" aria-hidden="true">
            <MessageCircle className="size-6" />
          </span>
          <p className="text-sm text-paper/55">{t("startWith")}</p>
          <div className="mt-4 flex flex-wrap justify-center gap-2">
            {suggestions.map((suggestion) => (
              <Button
                key={suggestion}
                type="button"
                variant="outline"
                size="sm"
                className="border-border bg-background text-foreground hover:border-primary/60 hover:bg-secondary hover:text-primary"
                onClick={() => onSuggestion(suggestion)}
              >
                “{suggestion}”
              </Button>
            ))}
          </div>
        </m.div>
      ) : (
        <AnimatePresence initial={false} mode="popLayout">
          {messages.map((message) => (
            <m.div
              key={message.id}
              layout
              initial={{ opacity: 0, y: 12, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, scale: 0.98 }}
              transition={{ duration: motionTokens.standard, ease: motionTokens.ease }}
              className={`flex gap-3 ${message.role === "caller" ? "justify-end" : "justify-start"}`}
              aria-label={message.role === "caller" ? t("yourMessage") : t("sahaayakMessage")}
            >
              <div className={`max-w-[88%] sm:max-w-[75%] ${message.role === "caller" ? "text-right" : "text-left"}`}>
                <span className="mb-1 block text-sm font-semibold text-muted-foreground">
                  {message.role === "caller" ? t("guest") : "sahaayak"}
                </span>
                <p
                  className={`rounded-2xl px-4 py-3 text-sm leading-6 ${
                    message.role === "caller"
                      ? "rounded-br-sm bg-primary text-primary-foreground"
                      : "rounded-bl-sm border border-border bg-muted/60 text-foreground"
                  }`}
                >
                  {message.text}
                </p>
              </div>
            </m.div>
          ))}
        </AnimatePresence>
      )}

      {isSending && (
        <m.div
          className="flex gap-3"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: motionTokens.standard, ease: motionTokens.ease }}
        >
          <div role="status" aria-label={t("preparingResponse")}>
            <span className="mb-1 block text-sm font-semibold text-muted-foreground">sahaayak</span>
            <div className="flex items-center gap-1 rounded-lg rounded-bl-sm border border-border bg-muted/60 px-4 py-4" aria-hidden="true">
              {[0, 1, 2].map((index) => <i key={index} className="size-1.5 rounded-full bg-primary" />)}
            </div>
          </div>
        </m.div>
      )}
    </div>
  );
}
