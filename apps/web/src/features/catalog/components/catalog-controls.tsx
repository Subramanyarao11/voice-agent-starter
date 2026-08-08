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
    <fieldset className="grid gap-3 rounded-2xl border border-paper/10 bg-paper/[0.04] p-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
      <legend className="sr-only">{t("conversationPreferences")}</legend>
      <label className="grid gap-1.5">
        <span className="px-1 font-mono text-[0.6rem] uppercase tracking-[0.18em] text-paper/45">{t("language")}</span>
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
        <span className="px-1 font-mono text-[0.6rem] uppercase tracking-[0.18em] text-paper/45">{t("state")}</span>
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
        className="flex h-10 items-center gap-2 rounded-lg border border-acid/20 bg-acid/10 px-3 text-xs text-acid sm:min-w-32"
        role="status"
        aria-live="polite"
        aria-label={t("benefitsAvailableIn", {count: stateCoverage, state: stateName ?? stateCode})}
      >
        <span className="size-2 rounded-full bg-acid" aria-hidden="true" />
        <span>
          <strong className="font-mono text-sm">{stateCoverage}</strong> {t("benefitsInState", {state: stateName ?? stateCode})}
        </span>
      </div>
    </fieldset>
  );
}
