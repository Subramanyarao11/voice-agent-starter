import { createContext, useContext, useEffect, useMemo, type ReactNode } from "react";

import { useConversationStore } from "@/features/conversation/store";
import {
  createUiTranslator,
  localeHtml,
  type UiBundleReviewStatus,
  type UiLocale,
  type UiTranslator,
} from "@/lib/i18n";

type UiContextValue = {
  locale: UiLocale;
  reviewStatus: UiBundleReviewStatus;
  t: UiTranslator;
};

const UiContext = createContext<UiContextValue | null>(null);

export function UiProvider({ children }: { children: ReactNode }) {
  const languageCode = useConversationStore((state) => state.languageCode);
  const value = useMemo(() => createUiTranslator(languageCode), [languageCode]);

  useEffect(() => {
    document.documentElement.lang = localeHtml(value.locale);
  }, [value.locale]);

  return <UiContext.Provider value={value}>{children}</UiContext.Provider>;
}

export function useUi(): UiContextValue {
  const value = useContext(UiContext);
  if (!value) throw new Error("useUi must be used inside UiProvider");
  return value;
}
