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

const localeFontLoaders: Partial<Record<UiLocale, () => Promise<unknown>>> = {
  bn: () => import("@fontsource-variable/noto-sans-bengali/wght.css"),
  gu: () => import("@fontsource-variable/noto-sans-gujarati/wght.css"),
  ml: () => import("@fontsource-variable/noto-sans-malayalam/wght.css"),
  or: () => import("@fontsource-variable/noto-sans-oriya/wght.css"),
  pa: () => import("@fontsource-variable/noto-sans-gurmukhi/wght.css"),
  ta: () => import("@fontsource-variable/noto-sans-tamil/wght.css"),
  te: () => import("@fontsource-variable/noto-sans-telugu/wght.css"),
};

export function UiProvider({ children }: { children: ReactNode }) {
  const languageCode = useConversationStore((state) => state.languageCode);
  const value = useMemo(() => createUiTranslator(languageCode), [languageCode]);

  useEffect(() => {
    document.documentElement.lang = localeHtml(value.locale);
  }, [value.locale]);

  useEffect(() => {
    const loadFont = localeFontLoaders[value.locale];
    if (loadFont) void loadFont();
  }, [value.locale]);

  return <UiContext.Provider value={value}>{children}</UiContext.Provider>;
}

export function useUi(): UiContextValue {
  const value = useContext(UiContext);
  if (!value) throw new Error("useUi must be used inside UiProvider");
  return value;
}
