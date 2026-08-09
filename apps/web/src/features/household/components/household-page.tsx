import { useEffect, useState, type FormEvent } from "react";

import { Link } from "@tanstack/react-router";
import {
  ArrowRight,
  Check,
  ExternalLink,
  LogIn,
  LogOut,
  RefreshCw,
  ShieldCheck,
  Users,
} from "lucide-react";

import { PublicFooter, Topbar } from "@/components/app/topbar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useUi } from "@/features/i18n/ui-provider";
import { beginCitizenOidcLogin, isCitizenOidcConfigured, signOutCitizen } from "@/features/citizen/oidc";
import { useCitizenWorkspaceStore } from "@/features/citizen/store";
import {
  citizenMeQueryKey,
  useAddMemberMutation,
  useCitizenMeQuery,
  useCreateHouseholdMutation,
  useFactsQuery,
  useHouseholdsQuery,
  useMembersQuery,
  useRadarActionMutation,
  useRadarQuery,
  useRefreshRadarMutation,
  useWriteMemberFactMutation,
} from "@/features/citizen/queries";
import { useCatalogQuery } from "@/features/catalog/queries";
import { ApiError, toUserMessage, type HouseholdMember, type ProfileFact, type RadarRecommendation } from "@/lib/api";
import { useQueryClient } from "@tanstack/react-query";

function textFromLocale(values: Record<string, string>, fallback: string): string {
  return values.en || Object.values(values)[0] || fallback;
}

function formatDate(value: string | null): string {
  if (!value) return "Not verified";
  const date = new Date(value.includes("T") ? value : `${value}T00:00:00`);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString(undefined, { dateStyle: "medium" });
}

function HouseholdError({ error }: { error: unknown }) {
  return (
    <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm leading-6">
      {toUserMessage(error)}
    </p>
  );
}

function SignInPanel({ onSignIn, pending }: { onSignIn: () => void; pending: boolean }) {
  const configured = isCitizenOidcConfigured();
  return (
    <Card className="border-primary/30 bg-primary/5">
      <CardHeader>
        <Badge variant="outline" className="w-fit border-primary/40 text-primary">
          Citizen workspace
        </Badge>
        <CardTitle className="text-2xl">Keep your household help in one place.</CardTitle>
        <CardDescription className="max-w-2xl text-base leading-7">
          Sign in to save household members and confirmed facts. Sahaayak uses them to find relevant benefits and shows the evidence behind each recommendation.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {configured ? (
          <Button onClick={onSignIn} disabled={pending} className="gap-2">
            <LogIn className="size-4" aria-hidden="true" />
            {pending ? "Opening secure sign-in…" : "Sign in securely"}
          </Button>
        ) : (
          <div className="rounded-lg border border-warning/40 bg-warning/10 p-4 text-sm leading-6">
            <p className="font-semibold">Citizen sign-in is not enabled for this web deployment.</p>
            <p className="mt-1 text-muted-foreground">
              Configure the citizen OIDC issuer, public client, BFF flag, redirect URI, and server encryption key before enabling this workspace.
            </p>
          </div>
        )}
        <p className="flex items-start gap-2 text-sm text-muted-foreground">
          <ShieldCheck className="mt-0.5 size-4 shrink-0 text-success" aria-hidden="true" />
          Provider tokens stay in an encrypted server session. This browser never stores a citizen access token.
        </p>
      </CardContent>
    </Card>
  );
}

function HouseholdSetup({ onCreated }: { onCreated: (id: string) => void }) {
  const catalogQuery = useCatalogQuery();
  const createMutation = useCreateHouseholdMutation();
  const [label, setLabel] = useState("My household");
  const [stateCode, setStateCode] = useState("KA");
  const [district, setDistrict] = useState("");
  const [pincode, setPincode] = useState("");
  const [personalization, setPersonalization] = useState(true);

  const states = catalogQuery.data?.states.filter((state) => state.is_active) ?? [];
  const submit = (event: FormEvent) => {
    event.preventDefault();
    createMutation.mutate(
      {
        label: label.trim() || "My household",
        state_code: stateCode || undefined,
        district: district.trim() || undefined,
        pincode: pincode.trim() || undefined,
        include_self: true,
        consent_persistence: true,
        consent_personalization: personalization,
      },
      { onSuccess: (household) => onCreated(household.id) },
    );
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Set up your household</CardTitle>
        <CardDescription>
          You control these details. They are used only for the purposes you confirm and can be deleted from the account later.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form className="grid gap-5 md:grid-cols-2" onSubmit={submit}>
          <label className="grid gap-2 text-sm font-semibold">
            Household name
            <input className="min-h-11 rounded-md border bg-background px-3 font-normal" value={label} onChange={(event) => setLabel(event.target.value)} />
          </label>
          <label className="grid gap-2 text-sm font-semibold">
            State
            <select className="min-h-11 rounded-md border bg-background px-3 font-normal" value={stateCode} onChange={(event) => setStateCode(event.target.value)}>
              {states.length === 0 && <option value="KA">Karnataka</option>}
              {states.map((state) => <option key={state.code} value={state.code}>{state.name}</option>)}
            </select>
          </label>
          <label className="grid gap-2 text-sm font-semibold">
            District <span className="font-normal text-muted-foreground">(optional)</span>
            <input className="min-h-11 rounded-md border bg-background px-3 font-normal" value={district} onChange={(event) => setDistrict(event.target.value)} placeholder="For example, Bengaluru Urban" />
          </label>
          <label className="grid gap-2 text-sm font-semibold">
            Pincode <span className="font-normal text-muted-foreground">(optional)</span>
            <input inputMode="numeric" maxLength={6} className="min-h-11 rounded-md border bg-background px-3 font-normal" value={pincode} onChange={(event) => setPincode(event.target.value.replace(/\D/g, ""))} placeholder="560001" />
          </label>
          <label className="flex items-start gap-3 text-sm leading-6 md:col-span-2">
            <input type="checkbox" className="mt-1 size-4 accent-primary" checked={personalization} onChange={(event) => setPersonalization(event.target.checked)} />
            <span>I agree to use these household facts for personalized benefit matching. I can withdraw this purpose later.</span>
          </label>
          {createMutation.error && <div className="md:col-span-2"><HouseholdError error={createMutation.error} /></div>}
          <div className="md:col-span-2">
            <Button type="submit" disabled={createMutation.isPending} className="gap-2">
              <Users className="size-4" aria-hidden="true" />
              {createMutation.isPending ? "Saving household…" : "Create household"}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

function MemberPicker({ members, selectedId, onChange }: { members: HouseholdMember[]; selectedId: string; onChange: (id: string) => void }) {
  return (
    <label className="grid gap-2 text-sm font-semibold">
      View recommendations for
      <select className="min-h-11 rounded-md border bg-background px-3 font-normal" value={selectedId} onChange={(event) => onChange(event.target.value)}>
        {members.map((member) => <option key={member.id} value={member.id}>{member.alias || member.safe_ordinal}</option>)}
      </select>
    </label>
  );
}

function AddMemberCard({ householdId }: { householdId: string }) {
  const addMutation = useAddMemberMutation(householdId);
  const [alias, setAlias] = useState("");
  const [relationship, setRelationship] = useState("spouse_partner");
  const [ageClass, setAgeClass] = useState("adult");
  const [authority, setAuthority] = useState(false);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    addMutation.mutate(
      {
        alias: alias.trim() || "Member",
        relationship_category: relationship,
        age_class: ageClass,
        authority_confirmed: authority,
        consent_member_management: true,
      },
      { onSuccess: () => { setAlias(""); setAuthority(false); } },
    );
  };
  return (
    <Card>
      <CardHeader><CardTitle className="text-lg">Add a household member</CardTitle><CardDescription>Only add someone you are authorized to manage.</CardDescription></CardHeader>
      <CardContent>
        <form className="grid gap-4 sm:grid-cols-3" onSubmit={submit}>
          <label className="grid gap-2 text-sm font-semibold sm:col-span-3">Name or safe alias<input className="min-h-11 rounded-md border bg-background px-3 font-normal" value={alias} onChange={(event) => setAlias(event.target.value)} placeholder="For example, Amma" /></label>
          <label className="grid gap-2 text-sm font-semibold">Relationship<select className="min-h-11 rounded-md border bg-background px-3 font-normal" value={relationship} onChange={(event) => setRelationship(event.target.value)}><option value="spouse_partner">Spouse/partner</option><option value="parent">Parent</option><option value="sibling">Sibling</option><option value="other">Other</option><option value="dependant">Dependant</option></select></label>
          <label className="grid gap-2 text-sm font-semibold">Age group<select className="min-h-11 rounded-md border bg-background px-3 font-normal" value={ageClass} onChange={(event) => setAgeClass(event.target.value)}><option value="unknown">Prefer not to say</option><option value="child">Child</option><option value="youth">Youth</option><option value="adult">Adult</option><option value="senior">Senior</option></select></label>
          <label className="flex items-start gap-3 text-sm leading-6 sm:col-span-3"><input type="checkbox" className="mt-1 size-4 accent-primary" checked={authority} onChange={(event) => setAuthority(event.target.checked)} /><span>I confirm I have authority to manage this member’s profile.</span></label>
          {addMutation.error && <div className="sm:col-span-3"><HouseholdError error={addMutation.error} /></div>}
          <div className="sm:col-span-3"><Button type="submit" disabled={addMutation.isPending}>{addMutation.isPending ? "Adding…" : "Add member"}</Button></div>
        </form>
      </CardContent>
    </Card>
  );
}

function FactsCard({ householdId, memberId }: { householdId: string; memberId: string }) {
  const factsQuery = useFactsQuery(householdId, memberId);
  const writeMutation = useWriteMemberFactMutation(householdId, memberId);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const facts = factsQuery.data ?? [];
  const writeFact = (fact: ProfileFact) => {
    const value = (drafts[fact.fact_key] ?? "").trim();
    if (!value) return;
    writeMutation.mutate({ factKey: fact.fact_key, value, purposes: ["benefit_matching"], expectedRevision: fact.revision ?? undefined });
  };
  return (
    <Card>
      <CardHeader><CardTitle className="text-lg">Confirmed facts</CardTitle><CardDescription>Missing or stale facts reduce confidence. Values are encrypted and the UI only receives masked values back.</CardDescription></CardHeader>
      <CardContent className="space-y-4">
        {factsQuery.isPending && <p role="status" className="text-sm text-muted-foreground">Loading governed questions…</p>}
        {factsQuery.error && <HouseholdError error={factsQuery.error} />}
        {facts.map((fact) => {
          const question = textFromLocale(fact.question, fact.fact_key);
          const current = drafts[fact.fact_key] ?? "";
          return (
            <div key={fact.fact_key} className="grid gap-3 rounded-lg border p-4 sm:grid-cols-[1fr_minmax(14rem,20rem)_auto] sm:items-end">
              <div>
                <div className="flex flex-wrap items-center gap-2"><p className="font-semibold">{question}</p><Badge variant={fact.state === "current" ? "success" : fact.state === "stale" ? "warning" : "outline"}>{fact.state}</Badge></div>
                <p className="mt-1 text-sm text-muted-foreground">{fact.masked_value ? `Saved value: ${fact.masked_value}` : "No value saved yet."}</p>
              </div>
              {fact.allowed_values.length > 0 ? (
                <select className="min-h-11 rounded-md border bg-background px-3" value={current} onChange={(event) => setDrafts((previous) => ({ ...previous, [fact.fact_key]: event.target.value }))} aria-label={question}><option value="">Choose an answer</option>{fact.allowed_values.map((value) => <option key={value} value={value}>{value}</option>)}</select>
              ) : (
                <input className="min-h-11 rounded-md border bg-background px-3" value={current} onChange={(event) => setDrafts((previous) => ({ ...previous, [fact.fact_key]: event.target.value }))} aria-label={question} placeholder="Enter an answer" />
              )}
              <Button type="button" variant="outline" disabled={!current.trim() || writeMutation.isPending} onClick={() => writeFact(fact)}>{writeMutation.isPending ? "Saving…" : "Save fact"}</Button>
            </div>
          );
        })}
        {writeMutation.error && <HouseholdError error={writeMutation.error} />}
        {facts.length === 0 && !factsQuery.isPending && <p className="text-sm text-muted-foreground">No reviewed fact questions are available yet.</p>}
      </CardContent>
    </Card>
  );
}

function RecommendationCard({ recommendation, onAction }: { recommendation: RadarRecommendation; onAction: (action: "view" | "dismiss") => void }) {
  const evidence = recommendation.criterion_evidence;
  return (
    <Card className="border-border">
      <CardHeader className="gap-3 pb-3">
        <div className="flex flex-wrap items-center justify-between gap-2"><Badge variant={recommendation.verdict === "eligible" ? "success" : recommendation.verdict === "uncertain" ? "warning" : "outline"}>{recommendation.verdict}</Badge><span className="text-sm text-muted-foreground">{Math.round(recommendation.confidence * 100)}% confidence</span></div>
        <CardTitle className="text-xl leading-snug">{recommendation.benefit_name}</CardTitle>
        <CardDescription>{recommendation.domain} · {recommendation.source_title || "Official source record"}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="rounded-lg bg-muted/60 p-4 text-sm leading-6">
          <p className="font-semibold">{recommendation.verdict === "uncertain" ? "Why this is uncertain" : "Why this matched"}</p>
          <ul className="mt-2 list-disc space-y-1 pl-5">{evidence.length > 0 ? evidence.map((item) => <li key={`${item.slot}-${item.fact_key}`}>{item.requirement}: <span className="font-semibold">{item.status}</span> ({item.fact_state})</li>) : <li>No criterion evidence was returned.</li>}</ul>
        </div>
        <div className="flex flex-wrap items-center gap-3 text-sm"><span>Source verified: {formatDate(recommendation.source_last_verified_date)}</span>{recommendation.source_url && <a className="inline-flex items-center gap-1 font-semibold text-primary underline-offset-4 hover:underline" href={recommendation.source_url} target="_blank" rel="noreferrer">Open source <ExternalLink className="size-3.5" aria-hidden="true" /></a>}</div>
        <div className="flex flex-wrap gap-2"><Link to="/benefits/$benefitId" params={{ benefitId: recommendation.benefit_id }} className="inline-flex min-h-11 items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground">View benefit <ArrowRight className="size-4" aria-hidden="true" /></Link><Button type="button" variant="outline" onClick={() => onAction("view")}><Check className="mr-2 size-4" aria-hidden="true" />Mark viewed</Button><Button type="button" variant="ghost" onClick={() => onAction("dismiss")}>Not useful</Button></div>
      </CardContent>
    </Card>
  );
}

function RadarCard({ householdId, memberId }: { householdId: string; memberId: string }) {
  const radarQuery = useRadarQuery(householdId, memberId);
  const refreshMutation = useRefreshRadarMutation(householdId, memberId);
  const actionMutation = useRadarActionMutation(householdId, memberId);
  const recommendations = radarQuery.data?.recommendations ?? [];
  return (
    <Card>
      <CardHeader className="gap-3 sm:flex-row sm:items-start sm:justify-between"><div><CardTitle className="text-xl">Household Benefits Radar</CardTitle><CardDescription className="mt-1">Only active, fresh, human-verified records are considered. This is guidance, not an official eligibility decision.</CardDescription></div><Button type="button" variant="outline" className="gap-2" disabled={refreshMutation.isPending} onClick={() => refreshMutation.mutate()}><RefreshCw className={`size-4 ${refreshMutation.isPending ? "animate-spin" : ""}`} aria-hidden="true" />{refreshMutation.isPending ? "Checking…" : "Refresh radar"}</Button></CardHeader>
      <CardContent className="space-y-4">
        {radarQuery.isPending && <p role="status" className="text-sm text-muted-foreground">Loading saved recommendations…</p>}
        {radarQuery.error && <HouseholdError error={radarQuery.error} />}
        {refreshMutation.error && <HouseholdError error={refreshMutation.error} />}
        {recommendations.length === 0 && !radarQuery.isPending && <div className="rounded-lg border border-dashed p-6 text-sm leading-6 text-muted-foreground"><p className="font-semibold text-foreground">No recommendations yet.</p><p className="mt-1">Add a few confirmed facts, then refresh the radar. Uncertain answers will remain visibly uncertain.</p></div>}
        {recommendations.map((recommendation) => <RecommendationCard key={recommendation.id} recommendation={recommendation} onAction={(action) => actionMutation.mutate({ recommendationId: recommendation.id, action })} />)}
      </CardContent>
    </Card>
  );
}

export function HouseholdPage() {
  const { t } = useUi();
  const queryClient = useQueryClient();
  const meQuery = useCitizenMeQuery();
  const authenticated = Boolean(meQuery.data);
  const householdsQuery = useHouseholdsQuery(authenticated);
  const householdId = useCitizenWorkspaceStore((state) => state.activeHouseholdId);
  const memberId = useCitizenWorkspaceStore((state) => state.activeMemberId);
  const setActiveHousehold = useCitizenWorkspaceStore((state) => state.setActiveHousehold);
  const setActiveMember = useCitizenWorkspaceStore((state) => state.setActiveMember);
  const clearWorkspace = useCitizenWorkspaceStore((state) => state.clearWorkspace);
  const membersQuery = useMembersQuery(householdId);
  const [signInPending, setSignInPending] = useState(false);
  const [signInError, setSignInError] = useState<string | null>(null);
  const [signOutPending, setSignOutPending] = useState(false);

  const households = householdsQuery.data ?? [];
  const activeHousehold = households.find((household) => household.id === householdId) ?? households[0];
  const members = membersQuery.data ?? [];
  const activeMember = members.find((member) => member.id === memberId) ?? members[0];

  useEffect(() => {
    if (activeHousehold && activeHousehold.id !== householdId) setActiveHousehold(activeHousehold.id);
  }, [activeHousehold, householdId, setActiveHousehold]);
  useEffect(() => {
    if (activeMember && activeMember.id !== memberId) setActiveMember(activeMember.id);
  }, [activeMember, memberId, setActiveMember]);

  const signIn = async () => {
    setSignInPending(true);
    setSignInError(null);
    try { await beginCitizenOidcLogin(); } catch (error) { setSignInError(toUserMessage(error)); setSignInPending(false); }
  };
  const signOut = async () => {
    setSignOutPending(true);
    try { await signOutCitizen(); clearWorkspace(); queryClient.removeQueries({ queryKey: citizenMeQueryKey }); } finally { setSignOutPending(false); }
  };

  const pageError = meQuery.error && !(meQuery.error instanceof ApiError && meQuery.error.status === 401) ? meQuery.error : householdsQuery.error;
  return (
    <div className="min-h-svh bg-background text-foreground">
      <Topbar sessionId="" connected={authenticated} activeSection="household" />
      <main id="main-content" tabIndex={-1} className="outline-none">
        <div className="mx-auto max-w-[1200px] space-y-8 px-4 py-10 sm:px-6 sm:py-14 lg:px-8">
          <header className="flex flex-wrap items-start justify-between gap-5">
            <div><p className="text-xs font-semibold uppercase tracking-[0.16em] text-primary">{t("savedWork")}</p><h1 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">Household help, with evidence</h1><p className="mt-3 max-w-2xl text-base leading-7 text-muted-foreground">Add only the facts you want to use. Sahaayak keeps the household view separate from the anonymous conversation and gives you control over recommendations.</p></div>
            {authenticated && <Button type="button" variant="outline" className="gap-2" disabled={signOutPending} onClick={() => void signOut()}><LogOut className="size-4" aria-hidden="true" />{signOutPending ? "Signing out…" : "Sign out"}</Button>}
          </header>
          {meQuery.isPending && <p role="status" className="text-sm text-muted-foreground">Checking your secure citizen session…</p>}
          {signInError && <HouseholdError error={signInError} />}
          {pageError && <HouseholdError error={pageError} />}
          {!authenticated && !meQuery.isPending && <SignInPanel onSignIn={() => void signIn()} pending={signInPending} />}
          {authenticated && householdsQuery.isPending && <p role="status" className="text-sm text-muted-foreground">Loading your household…</p>}
          {authenticated && !householdsQuery.isPending && households.length === 0 && <HouseholdSetup onCreated={setActiveHousehold} />}
          {authenticated && activeHousehold && <section className="space-y-6" aria-labelledby="household-heading"><div className="flex flex-wrap items-end justify-between gap-4"><div><p className="text-sm font-semibold text-primary">{activeHousehold.state_code || "India"}{activeHousehold.district ? ` · ${activeHousehold.district}` : ""}</p><h2 id="household-heading" className="mt-1 text-2xl font-bold">{activeHousehold.label}</h2><p className="mt-1 text-sm text-muted-foreground">{activeHousehold.member_count} member{activeHousehold.member_count === 1 ? "" : "s"} · matching policy {activeHousehold.matching_policy_version}</p></div>{members.length > 0 && <div className="min-w-[16rem]"><MemberPicker members={members} selectedId={activeMember?.id ?? ""} onChange={setActiveMember} /></div>}</div>{membersQuery.error && <HouseholdError error={membersQuery.error} />}{activeMember && <><FactsCard householdId={activeHousehold.id} memberId={activeMember.id} /><RadarCard householdId={activeHousehold.id} memberId={activeMember.id} /></>}<AddMemberCard householdId={activeHousehold.id} /></section>}
        </div>
      </main>
      <PublicFooter />
    </div>
  );
}
