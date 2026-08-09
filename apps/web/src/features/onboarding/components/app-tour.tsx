import { useEffect, useRef, useState, type CSSProperties } from "react";

import { ArrowLeft, ArrowRight, Check, X } from "lucide-react";
import { m } from "motion/react";

import { Button } from "@/components/ui/button";
import { useUi } from "@/features/i18n/ui-provider";
import { useAppTourStore } from "@/features/onboarding/store";
import { motionTokens } from "@/lib/motion";
import type { UiKey } from "@/lib/i18n";

const TOUR_STEPS: Array<{
  title: UiKey;
  description: UiKey;
  target?: string;
}> = [
  {
    title: "tourWelcomeTitle",
    description: "tourWelcomeDescription",
  },
  {
    title: "tourPreferencesTitle",
    description: "tourPreferencesDescription",
    target: "preferences",
  },
  {
    title: "tourConversationTitle",
    description: "tourConversationDescription",
    target: "conversation",
  },
  {
    title: "tourResultsTitle",
    description: "tourResultsDescription",
    target: "results",
  },
];

function focusableElements(container: HTMLElement): HTMLElement[] {
  return Array.from(
    container.querySelectorAll<HTMLElement>(
      'button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    ),
  );
}

export function AppTour() {
  const { t } = useUi();
  const hasSeenTour = useAppTourStore((state) => state.hasSeenTour);
  const markTourSeen = useAppTourStore((state) => state.markTourSeen);
  const [isMounted, setIsMounted] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [stepIndex, setStepIndex] = useState(0);
  const [targetRect, setTargetRect] = useState<DOMRect | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  useEffect(() => {
    if (!isMounted || hasSeenTour) return;
    // Mark the tour as seen when it opens, not only when the final button is
    // pressed. Refreshing halfway through should not repeatedly interrupt a
    // returning citizen.
    markTourSeen();
    setIsOpen(true);
  }, [hasSeenTour, isMounted, markTourSeen]);

  useEffect(() => {
    if (!isOpen) return;
    const previousActiveElement = document.activeElement as HTMLElement | null;
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setIsOpen(false);
        return;
      }
      if (event.key !== "Tab" || !dialogRef.current) return;

      const elements = focusableElements(dialogRef.current);
      if (elements.length === 0) {
        event.preventDefault();
        dialogRef.current.focus();
        return;
      }
      const first = elements[0];
      const last = elements[elements.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    window.requestAnimationFrame(() => closeButtonRef.current?.focus());

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = originalOverflow;
      if (previousActiveElement?.isConnected) previousActiveElement.focus();
    };
  }, [isOpen, stepIndex]);

  useEffect(() => {
    if (!isOpen) return;
    const step = TOUR_STEPS[stepIndex];
    const updateTargetRect = () => {
      if (!step.target) {
        setTargetRect(null);
        return;
      }
      const element = document.querySelector<HTMLElement>(`[data-tour="${step.target}"]`);
      if (!element) {
        setTargetRect(null);
        return;
      }
      const rect = element.getBoundingClientRect();
      setTargetRect(rect.width > 0 && rect.height > 0 ? rect : null);
    };

    const target = step.target
      ? document.querySelector<HTMLElement>(`[data-tour="${step.target}"]`)
      : null;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    target?.scrollIntoView({
      block: "nearest",
      inline: "nearest",
      behavior: reducedMotion ? "auto" : "smooth",
    });
    updateTargetRect();
    const frame = window.requestAnimationFrame(updateTargetRect);
    window.addEventListener("resize", updateTargetRect);
    window.addEventListener("scroll", updateTargetRect, true);
    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener("resize", updateTargetRect);
      window.removeEventListener("scroll", updateTargetRect, true);
    };
  }, [isOpen, stepIndex]);

  if (!isMounted || !isOpen) return null;

  const step = TOUR_STEPS[stepIndex];
  const isFirstStep = stepIndex === 0;
  const isLastStep = stepIndex === TOUR_STEPS.length - 1;
  const highlightStyle: CSSProperties | undefined = targetRect
    ? {
        top: Math.max(8, targetRect.top - 8),
        left: Math.max(8, targetRect.left - 8),
        width: Math.min(window.innerWidth - 16, targetRect.width + 16),
        height: Math.min(window.innerHeight - 16, targetRect.height + 16),
      }
    : undefined;

  function closeTour() {
    setIsOpen(false);
  }

  function goNext() {
    if (isLastStep) {
      closeTour();
      return;
    }
    setStepIndex((current) => current + 1);
  }

  function goBack() {
    setStepIndex((current) => Math.max(0, current - 1));
  }

  return (
    <div className="fixed inset-0 z-[100]" data-tour-overlay>
      <div className={targetRect ? "absolute inset-0" : "absolute inset-0 bg-foreground/65"} aria-hidden="true" />
      {highlightStyle && (
        <div
          className="pointer-events-none absolute rounded-xl border-2 border-primary-foreground shadow-[0_0_0_9999px_rgb(21_2_2_/_0.65)]"
          style={highlightStyle}
          aria-hidden="true"
        />
      )}

      <m.div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={t("tourLabel")}
        aria-labelledby="sahaayak-tour-title"
        aria-describedby="sahaayak-tour-description"
        tabIndex={-1}
        className="absolute inset-x-4 bottom-4 mx-auto max-w-xl rounded-2xl border border-primary/25 bg-card p-5 text-card-foreground shadow-2xl sm:inset-x-auto sm:right-6 sm:bottom-6 sm:w-[min(30rem,calc(100vw-3rem))] sm:p-6"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: motionTokens.standard, ease: motionTokens.ease }}
      >
        <div className="flex items-start justify-between gap-4">
          <p aria-live="polite" className="text-sm font-semibold text-primary">
            {t("tourStep", { current: stepIndex + 1, total: TOUR_STEPS.length })}
          </p>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={closeTour}
            className="grid size-11 shrink-0 place-items-center rounded-lg text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground focus-visible:outline-3 focus-visible:outline-offset-2 focus-visible:outline-ring"
            aria-label={t("tourClose")}
            title={t("tourClose")}
          >
            <X className="size-5" aria-hidden="true" />
          </button>
        </div>

        <div className="mt-1 flex gap-1.5" aria-hidden="true">
          {TOUR_STEPS.map((tourStep, index) => (
            <span
              key={tourStep.title}
              className={`h-1.5 flex-1 rounded-full ${index <= stepIndex ? "bg-primary" : "bg-border"}`}
            />
          ))}
        </div>

        <h2 id="sahaayak-tour-title" className="mt-5 text-xl font-bold tracking-tight sm:text-2xl">
          {t(step.title)}
        </h2>
        <p id="sahaayak-tour-description" className="mt-3 text-base leading-7 text-muted-foreground">
          {t(step.description)}
        </p>

        <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
          <Button type="button" variant="ghost" size="sm" onClick={closeTour}>
            {t("tourSkip")}
          </Button>
          <div className="flex items-center gap-2">
            {!isFirstStep && (
              <Button type="button" variant="outline" size="sm" onClick={goBack}>
                <ArrowLeft className="size-4" aria-hidden="true" />
                {t("tourBack")}
              </Button>
            )}
            <Button type="button" size="sm" onClick={goNext}>
              {isLastStep ? <Check className="size-4" aria-hidden="true" /> : null}
              {isLastStep ? t("tourFinish") : t("tourNext")}
              {!isLastStep ? <ArrowRight className="size-4" aria-hidden="true" /> : null}
            </Button>
          </div>
        </div>
      </m.div>
    </div>
  );
}
