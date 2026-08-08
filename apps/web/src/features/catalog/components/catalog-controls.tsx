import type { Language, State } from "@/lib/api";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useUi } from "@/features/i18n/ui-provider";

type CatalogControlsProps = {
  languages: Language[];
  states: State[];
  languageCode: string;
  stateCode: string;
  stateName?: string;
  stateCoverage: number;
  disabled: boolean;
  onLanguageChange: (value: string) => void;
  onStateChange: (value: string) => void;
};

export function CatalogControls({
  languages,
  states,
  languageCode,
  stateCode,
  stateName,
  stateCoverage,
  disabled,
  onLanguageChange,
  onStateChange,
}: CatalogControlsProps) {
  const { t } = useUi();
  return (
    <fieldset id="conversation-preferences" className="grid scroll-mt-6 gap-4 rounded-lg border border-border bg-card p-4 shadow-sm sm:grid-cols-[1fr_1fr_auto] sm:items-end">
      <legend className="sr-only">{t("conversationPreferences")}</legend>
      <label className="grid gap-1.5">
        <span className="px-1 text-sm font-semibold text-foreground">{t("language")}</span>
        <Select value={languageCode} onValueChange={onLanguageChange} disabled={disabled}>
          <SelectTrigger aria-label={t("chooseLanguage")}>
            <SelectValue placeholder={t("chooseLanguage")} />
          </SelectTrigger>
          <SelectContent>
            {languages.map((language) => (
              <SelectItem value={language.code} key={language.code}>
                {language.native_name} · {language.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </label>

      <label className="grid gap-1.5">
        <span className="px-1 text-sm font-semibold text-foreground">{t("state")}</span>
        <Select value={stateCode} onValueChange={onStateChange} disabled={disabled}>
          <SelectTrigger aria-label={t("chooseState")}>
            <SelectValue placeholder={t("chooseState")} />
          </SelectTrigger>
          <SelectContent>
            {states.map((state) => (
              <SelectItem value={state.code} key={state.code}>
                {state.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </label>

      <div
        className="flex min-h-11 items-center gap-2 rounded border border-primary/30 bg-secondary px-3 text-sm text-secondary-foreground sm:min-w-40"
        role="status"
        aria-live="polite"
        aria-label={t("benefitsAvailableIn", {count: stateCoverage, state: stateName ?? stateCode})}
      >
        <span className="size-2.5 rounded-full bg-primary" aria-hidden="true" />
        <span>
          <strong className="font-bold">{stateCoverage}</strong> {t("benefitsInState", {state: stateName ?? stateCode})}
        </span>
      </div>
    </fieldset>
  );
}
