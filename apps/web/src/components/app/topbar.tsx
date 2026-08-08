import { Link } from "@tanstack/react-router";
import { Radio } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { useUi } from "@/features/i18n/ui-provider";

type TopbarProps = {
  sessionId: string;
  connected: boolean;
};

export function Topbar({ sessionId, connected }: TopbarProps) {
  const { t } = useUi();
  return (
    <header className="mx-auto flex max-w-[1440px] items-center justify-between gap-4" aria-label="Sahaayak status">
      <Link to="/" className="group flex items-center gap-3" aria-label="Sahaayak home">
        <span className="grid size-11 place-items-center rounded-xl bg-acid font-serif text-2xl font-bold text-ink shadow-[4px_4px_0_rgb(245_241_231_/_18%)] transition-transform group-hover:-translate-y-0.5">
          स
        </span>
        <span className="grid leading-none">
          <strong className="text-sm font-extrabold tracking-tight text-paper">Sahaayak</strong>
        <small className="mt-1 text-[0.6rem] uppercase tracking-[0.18em] text-blue/70">{t("brandTagline")}</small>
        </span>
      </Link>

      <div className="flex items-center gap-2 text-xs text-paper/65 sm:gap-3">
        <span className="inline-flex items-center gap-1.5" role="status" aria-live="polite">
          <span
            className={`size-2 rounded-full ${connected ? "bg-acid shadow-[0_0_12px_var(--acid)]" : "bg-orange"}`}
            aria-hidden="true"
          />
          <span className="hidden sm:inline">{connected ? t("apiConnected") : t("apiConnecting")}</span>
        </span>
        <Badge
          variant="outline"
          className="border-paper/15 bg-paper/5 font-mono text-[0.65rem] text-paper/70"
          aria-label={t("anonymousSession")}
        >
          <Radio className="size-3" aria-hidden="true" /> {t("guest")} · {sessionId ? sessionId.slice(-8) : t("starting")}
        </Badge>
      </div>
    </header>
  );
}
