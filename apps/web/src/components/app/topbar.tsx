import { CircleCheck, CircleHelp, Languages, ShieldCheck } from "lucide-react";
import { Link } from "@tanstack/react-router";

import { Badge } from "@/components/ui/badge";
import { useUi } from "@/features/i18n/ui-provider";

type TopbarProps = {
  sessionId: string;
  connected: boolean;
  currentLanguage?: string;
  activeSection?: "home" | "saved" | "applications";
};

export function Topbar({ sessionId, connected, currentLanguage, activeSection = "home" }: TopbarProps) {
  const { t } = useUi();

  return (
    <header className="border-b border-border bg-background" aria-label="Sahaayak site header">
      <div className="bg-primary text-primary-foreground">
        <div className="mx-auto flex min-h-10 max-w-[1200px] items-center justify-between gap-4 px-4 text-sm sm:px-6 lg:px-8">
          <a
            href="#main-content"
            className="sr-only rounded bg-primary-foreground px-3 py-2 font-semibold text-primary focus:not-sr-only focus:outline-none"
          >
            {t("skipToMainContent")}
          </a>
          <nav className="ml-auto flex flex-wrap items-center justify-end gap-x-4 gap-y-1" aria-label="Utility navigation">
            <a className="inline-flex min-h-10 items-center gap-1.5 underline-offset-4 hover:underline" href="/#conversation-preferences">
              <Languages className="size-4" aria-hidden="true" />
              {t("utilityLanguage")}{currentLanguage ? `: ${currentLanguage}` : ""}
            </a>
            <a className="inline-flex min-h-10 items-center gap-1.5 underline-offset-4 hover:underline" href="/#accessibility-note">
              <ShieldCheck className="size-4" aria-hidden="true" />
              {t("accessibility")}
            </a>
            <a className="inline-flex min-h-10 items-center gap-1.5 underline-offset-4 hover:underline" href="/#help-note">
              <CircleHelp className="size-4" aria-hidden="true" />
              {t("help")}
            </a>
          </nav>
        </div>
      </div>

      <div className="mx-auto flex max-w-[1200px] flex-wrap items-center justify-between gap-4 px-4 py-4 sm:px-6 lg:px-8">
        <Link to="/" className="group flex min-h-11 items-center gap-3" aria-label="Sahaayak home">
          <span className="grid size-11 place-items-center rounded-lg bg-primary text-lg font-bold text-primary-foreground">
            S
          </span>
          <span className="grid gap-0.5">
            <strong className="text-lg font-bold tracking-tight text-foreground">Sahaayak</strong>
            <small className="text-sm text-muted-foreground">{t("independentDescriptor")}</small>
          </span>
        </Link>

        <div className="flex flex-wrap items-center justify-end gap-2 text-sm">
          <span className="inline-flex min-h-10 items-center gap-2" role="status" aria-live="polite">
            <span className={`size-2.5 rounded-full ${connected ? "bg-success" : "bg-warning"}`} aria-hidden="true" />
            <span>{connected ? t("serviceAvailable") : t("serviceConnecting")}</span>
          </span>
          {sessionId && (
            <Badge variant="outline" className="border-border bg-muted text-foreground">
              {t("guestSession")}
            </Badge>
          )}
        </div>
      </div>

      <nav className="mx-auto max-w-[1200px] overflow-x-auto px-4 sm:px-6 lg:px-8" aria-label="Primary navigation">
        <ul className="flex min-w-max gap-1">
          <li>
            <Link
              to="/"
              aria-current={activeSection === "home" ? "page" : undefined}
              className={`inline-flex min-h-11 items-center gap-2 border-b-4 px-3 text-sm font-semibold transition-colors ${
                activeSection === "home" ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              {t("home")}
            </Link>
          </li>
          <li>
            <a className="inline-flex min-h-11 items-center gap-2 border-b-4 border-transparent px-3 text-sm font-semibold text-muted-foreground transition-colors hover:text-foreground" href="/#conversation">
              {t("findBenefits")}
            </a>
          </li>
          <li>
            <a className="inline-flex min-h-11 items-center gap-2 border-b-4 border-transparent px-3 text-sm font-semibold text-muted-foreground transition-colors hover:text-foreground" href="/#saved-work">
              {t("savedWork")}
            </a>
          </li>
          <li>
            <Link
              to="/applications"
              aria-current={activeSection === "applications" ? "page" : undefined}
              className={`inline-flex min-h-11 items-center gap-2 border-b-4 px-3 text-sm font-semibold transition-colors ${
                activeSection === "applications"
                  ? "border-primary text-primary"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              My applications
            </Link>
          </li>
          <li>
            <Link
              to="/settings/data-usage"
              className="inline-flex min-h-11 items-center gap-2 border-b-4 border-transparent px-3 text-sm font-semibold text-muted-foreground transition-colors hover:text-foreground"
            >
              Data use
            </Link>
          </li>
          <li>
            <a className="inline-flex min-h-11 items-center gap-2 border-b-4 border-transparent px-3 text-sm font-semibold text-muted-foreground transition-colors hover:text-foreground" href="/#help-note">
              {t("help")}
            </a>
          </li>
        </ul>
      </nav>
    </header>
  );
}

export function PublicFooter() {
  const { t } = useUi();

  return (
    <footer className="border-t border-border bg-muted/40" aria-label="Sahaayak information and policy links">
      <div className="mx-auto grid max-w-[1200px] gap-6 px-4 py-10 sm:grid-cols-2 sm:px-6 lg:grid-cols-4 lg:px-8">
        <section id="about-note" aria-labelledby="about-note-title">
          <h2 id="about-note-title" className="text-base font-bold">{t("aboutSahaayak")}</h2>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">{t("aboutSahaayakDescription")}</p>
        </section>
        <section id="accessibility-note" aria-labelledby="accessibility-note-title">
          <h2 id="accessibility-note-title" className="text-base font-bold">{t("accessibility")}</h2>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">{t("accessibilitySummary")}</p>
        </section>
        <section id="privacy-note" aria-labelledby="privacy-note-title">
          <h2 id="privacy-note-title" className="text-base font-bold">Privacy and consent</h2>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">{t("privacySummary")}</p>
        </section>
        <section id="help-note" aria-labelledby="help-note-title">
          <h2 id="help-note-title" className="text-base font-bold">{t("help")}</h2>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">{t("helpSummary")}</p>
        </section>
      </div>
      <div className="border-t border-border">
        <div className="mx-auto flex max-w-[1200px] flex-wrap items-center justify-between gap-3 px-4 py-5 text-sm sm:px-6 lg:px-8">
          <p className="inline-flex items-center gap-2 font-semibold text-foreground">
            <CircleCheck className="size-4 text-success" aria-hidden="true" />
            {t("notGovernmentWebsite")}
          </p>
          <p className="text-muted-foreground">{t("footerUpdated")}</p>
        </div>
      </div>
    </footer>
  );
}
