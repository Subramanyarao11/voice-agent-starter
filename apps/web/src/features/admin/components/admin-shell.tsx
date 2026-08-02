import { useState, type FormEvent, type ReactNode } from "react";

import { Activity, ArrowLeft, Database, FileCheck2, Gauge, Languages, ListChecks, LogOut, Server, ShieldCheck, Users } from "lucide-react";
import { Link } from "@tanstack/react-router";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useAdminMeQuery } from "@/features/admin/queries";
import { useAdminSessionStore } from "@/features/admin/store";
import { toUserMessage } from "@/lib/api";

export type AdminView = "overview" | "conversations" | "telemetry" | "escalations" | "benefits" | "providers" | "languages" | "audit" | "system";

const NAV_ITEMS: Array<{ view: AdminView; label: string; href: string; icon: typeof Gauge }> = [
  {view: "overview", label: "Overview", href: "/admin/overview", icon: Gauge},
  {view: "conversations", label: "Conversations", href: "/admin/conversations", icon: Users},
  {view: "telemetry", label: "Telemetry", href: "/admin/telemetry", icon: Activity},
  {view: "escalations", label: "Escalations", href: "/admin/escalations", icon: ListChecks},
  {view: "benefits", label: "Benefits & review", href: "/admin/benefits", icon: FileCheck2},
  {view: "providers", label: "Providers", href: "/admin/providers", icon: Server},
  {view: "languages", label: "Languages", href: "/admin/languages", icon: Languages},
  {view: "audit", label: "Audit log", href: "/admin/audit-log", icon: ShieldCheck},
  {view: "system", label: "System", href: "/admin/system", icon: Database},
];

type AdminShellProps = {
  activeView: AdminView;
  children: ReactNode;
};

export function AdminShell({ activeView, children }: AdminShellProps) {
  const token = useAdminSessionStore((state) => state.token);
  const setToken = useAdminSessionStore((state) => state.setToken);
  const clearToken = useAdminSessionStore((state) => state.clearToken);
  const meQuery = useAdminMeQuery(token);

  if (!token) {
    return <AdminAccessGate onToken={setToken} />;
  }

  if (meQuery.isPending) {
    return <AdminLoading />;
  }

  if (meQuery.isError || !meQuery.data) {
    return <AdminAccessGate onToken={setToken} error={toUserMessage(meQuery.error)} onClear={clearToken} />;
  }

  return (
    <main className="min-h-svh bg-ink px-4 py-5 text-paper sm:px-8 lg:px-12" aria-labelledby="admin-title">
      <div className="mx-auto max-w-[1500px]">
        <header className="flex flex-wrap items-start justify-between gap-5 border-b border-paper/10 pb-6">
          <div>
            <Link to="/" className="inline-flex items-center gap-2 text-xs text-paper/50 hover:text-acid">
              <ArrowLeft className="size-3.5" aria-hidden="true" />
              Citizen experience
            </Link>
            <p className="mt-6 font-mono text-[0.62rem] uppercase tracking-[0.24em] text-acid">Sahaayak operations</p>
            <h1 id="admin-title" className="mt-2 text-3xl font-extrabold tracking-tight sm:text-5xl">Platform control center</h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-paper/55">
              Observe reliability, quality, provider spend, content provenance, and workforce actions from one redacted-by-default surface.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Badge variant="outline" className="border-acid/30 text-acid">
              <ShieldCheck className="size-3" aria-hidden="true" />
              {meQuery.data.role} · {meQuery.data.auth_source === "oidc" && meQuery.data.mfa_verified ? "MFA" : "local"}
            </Badge>
            <Button variant="ghost" size="sm" onClick={clearToken} aria-label="End admin session">
              <LogOut className="size-3.5" aria-hidden="true" />
              Sign out
            </Button>
          </div>
        </header>

        <nav className="mt-5 overflow-x-auto" aria-label="Admin sections">
          <ul className="flex min-w-max gap-2">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              const active = item.view === activeView;
              return (
                <li key={item.view}>
                  <Link
                    to={item.href}
                    aria-current={active ? "page" : undefined}
                    className={`inline-flex items-center gap-2 rounded-full border px-3 py-2 text-xs font-semibold transition ${
                      active
                        ? "border-acid/40 bg-acid/10 text-acid"
                        : "border-paper/10 text-paper/55 hover:border-paper/25 hover:text-paper"
                    }`}
                  >
                    <Icon className="size-3.5" aria-hidden="true" />
                    {item.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        <div className="mt-8">{children}</div>

        <footer className="mt-12 border-t border-paper/10 py-5 text-xs text-paper/40">
          <div className="flex flex-wrap justify-between gap-3">
            <span>Admin telemetry is redacted by default. Elevated access must be separately authorized and audited.</span>
            <span>actor · {meQuery.data.actor_id}</span>
          </div>
        </footer>
      </div>
    </main>
  );
}

function AdminAccessGate({ onToken, error, onClear }: { onToken: (token: string) => void; error?: string; onClear?: () => void }) {
  const [draft, setDraft] = useState("");
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (draft.trim()) onToken(draft);
  };

  return (
    <main className="grid min-h-svh place-items-center bg-ink px-5 text-paper" aria-labelledby="admin-access-title">
      <Card className="w-full max-w-lg border-acid/20 bg-paper/[0.04] text-paper">
        <CardContent className="space-y-6 p-6 sm:p-8">
          <div>
            <p className="font-mono text-[0.62rem] uppercase tracking-[0.22em] text-acid">Workforce access</p>
            <h1 id="admin-access-title" className="mt-3 text-3xl font-extrabold">Platform control center</h1>
            <p className="mt-3 text-sm leading-6 text-paper/60">
              Enter the deployment’s admin bearer token. It is kept in this browser tab’s session storage and is never displayed back to the page.
            </p>
          </div>
          {error && <p role="alert" className="rounded-xl border border-orange/30 bg-orange/10 px-4 py-3 text-sm text-orange">{error}</p>}
          <form className="space-y-3" onSubmit={submit} aria-label="Admin sign in">
            <label className="grid gap-2 text-sm font-semibold" htmlFor="admin-token">
              Admin token
              <input
                id="admin-token"
                type="password"
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                autoComplete="off"
                className="h-11 rounded-xl border border-paper/15 bg-ink px-3 text-paper outline-none focus-visible:ring-2 focus-visible:ring-acid"
              />
            </label>
            <Button type="submit" className="w-full bg-acid text-ink hover:bg-acid/90">Continue securely</Button>
          </form>
          <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-paper/45">
            <Link to="/" className="inline-flex items-center gap-2 hover:text-acid"><ArrowLeft className="size-3.5" aria-hidden="true" />Return to citizen app</Link>
            {onClear && <button type="button" onClick={onClear} className="underline underline-offset-4 hover:text-paper">Clear rejected session</button>}
          </div>
        </CardContent>
      </Card>
    </main>
  );
}

function AdminLoading() {
  return <main className="grid min-h-svh place-items-center bg-ink text-paper"><p role="status" className="text-sm text-paper/60">Checking workforce access…</p></main>;
}
