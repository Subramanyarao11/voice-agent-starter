import { useCallback, useMemo } from "react";

import type { TurnResponse } from "@/lib/api";
import { toUserMessage } from "@/lib/api";
import { ComparisonPanel } from "@/features/benefits/components/comparison-panel";
import { useCompareStore } from "@/features/benefits/compare-store";
import { ContactSettingsPanel } from "@/features/contacts/components/contact-settings-panel";
import { MatchesPanel } from "@/features/conversation/components/matches-panel";
import { SourcesPanel } from "@/features/conversation/components/sources-panel";
import { TurnInspector } from "@/features/conversation/components/turn-inspector";
import { SavedBenefitsPanel } from "@/features/saved/components/saved-benefits-panel";
import {
  useRemoveSavedBenefitMutation,
  useSaveBenefitMutation,
  useSavedBenefitsQuery,
} from "@/features/saved/queries";

type HomeResultsProps = {
  lastTurn: TurnResponse | null;
  sessionId: string;
  accessToken: string;
  languageCode: string;
  onError: (message: string) => void;
};

export default function HomeResults({
  lastTurn,
  sessionId,
  accessToken,
  languageCode,
  onError,
}: HomeResultsProps) {
  const savedBenefitsQuery = useSavedBenefitsQuery(sessionId, accessToken);
  const saveBenefitMutation = useSaveBenefitMutation(sessionId, accessToken);
  const removeSavedBenefitMutation = useRemoveSavedBenefitMutation(sessionId, accessToken);
  const comparedBenefitIds = useCompareStore((state) => state.benefitIds);
  const toggleCompare = useCompareStore((state) => state.toggle);

  const savedBenefitIds = useMemo(
    () => new Set(savedBenefitsQuery.data?.map((benefit) => benefit.benefit_id) ?? []),
    [savedBenefitsQuery.data],
  );

  const handleToggleSaved = useCallback(
    (benefitId: string, saved: boolean) => {
      const mutation = saved ? removeSavedBenefitMutation : saveBenefitMutation;
      mutation.mutate(benefitId, {
        onError: (error) => onError(toUserMessage(error)),
      });
    },
    [onError, removeSavedBenefitMutation, saveBenefitMutation],
  );

  return (
    <section id="results" className="mx-auto max-w-[1200px] space-y-8 px-4 pb-14 sm:px-6 lg:px-8">
      <MatchesPanel
        turn={lastTurn}
        savedBenefitIds={savedBenefitIds}
        onToggleSaved={handleToggleSaved}
        comparedBenefitIds={new Set(comparedBenefitIds)}
        onToggleCompare={(benefitId, compared) => {
          if (compared || comparedBenefitIds.length < 3) toggleCompare(benefitId);
        }}
      />
      <SourcesPanel turn={lastTurn} />
      <TurnInspector turn={lastTurn} />
      <ComparisonPanel />
      <section id="saved-work" className="scroll-mt-8">
        <SavedBenefitsPanel
          sessionId={sessionId}
          accessToken={accessToken}
          savedBenefits={savedBenefitsQuery.data ?? []}
        />
      </section>
      {(savedBenefitsQuery.data?.length ?? 0) > 0 && (
        <ContactSettingsPanel
          sessionId={sessionId}
          accessToken={accessToken}
          languageCode={languageCode}
        />
      )}
    </section>
  );
}
