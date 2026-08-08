import { useEffect, useState, type FormEvent, type ReactNode } from "react";

import { Activity, ArrowLeft, BarChart3, Database, FileCheck2, Flag, Gauge, Languages, ListChecks, LogOut, MapPinned, MessageSquare, Server, ShieldCheck, Users } from "lucide-react";
import { Link } from "@tanstack/react-router";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useAdminMeQuery } from "@/features/admin/queries";
import { useAdminSessionStore } from "@/features/admin/store";
import { toUserMessage } from "@/lib/api";
import {
  beginAdminOidcLogin,
  beginAdminOidcLogout,
  isAdminOidcConfigured,
} from "@/features/admin/oidc";

export type AdminView = "overview" | "conversations" | "telemetry" | "escalations" | "directory" | "benefits" | "providers" | "messaging" | "quality" | "flags" | "languages" | "audit" | "system";

const NAV_ITEMS: Array<{ view: AdminView; label: string; href: string; icon: typeof Gauge }> = [
  {view: "overview", label: "Overview", href: "/admin/overview", icon: Gauge},
  {view: "conversations", label: "Conversations", href: "/admin/conversations", icon: Users},
  {view: "telemetry", label: "Telemetry", href: "/admin/telemetry", icon: Activity},
  {view: "escalations", label: "Escalations", href: "/admin/escalations", icon: ListChecks},
  {view: "directory", label: "Directory", href: "/admin/directory", icon: MapPinned},
  {view: "benefits", label: "Benefits & review", href: "/admin/benefits", icon: FileCheck2},
  {view: "providers", label: "Providers", href: "/admin/providers", icon: Server},
  {view: "messaging", label: "Messaging", href: "/admin/messaging", icon: MessageSquare},
  {view: "quality", label: "Data & evals", href: "/admin/quality", icon: BarChart3},
  {view: "flags", label: "Feature flags", href: "/admin/flags", icon: Flag},
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
  const idToken = useAdminSessionStore((state) => state.idToken);
  const expiresAt = useAdminSessionStore((state) => state.expiresAt);
  const setToken = useAdminSessionStore((state) => state.setToken);
  const clearToken = useAdminSessionStore((state) => state.clearToken);
  const meQuery = useAdminMeQuery(token);
  const oidcConfigured = isAdminOidcConfigured();

  useEffect(() => {
    if (!token || expiresAt <= 0) return;
    const remaining = expiresAt - Date.now();
    if (remaining <= 0) {
      clearToken();
      return;
    }
    const timer = window.setTimeout(clearToken, remaining);
    return () => window.clearTimeout(timer);
  }, [clearToken, expiresAt, token]);

  if (!token) {
    return <AdminAccessGate onToken={setToken} oidcConfigured={oidcConfigured} />;
  }

  if (meQuery.isPending) {
    return <AdminLoading />;
  }

  if (meQuery.isError || !meQuery.data) {
    return <AdminAccessGate onToken={setToken} error={toUserMessage(meQuery.error)} onClear={clearToken} oidcConfigured={oidcConfigured} />;
  }

  return (
    <main className="min-h-svh bg-background text-foreground" aria-labelledby="admin-title">
      <div className="mx-auto grid max-w-[1440px] gap-6 px-4 py-4 sm:px-6 lg:grid-cols-[236px_minmax(0,1fr)] lg:gap-8 lg:px-8">
        <a
          href="#admin-content"
          className="sr-only rounded bg-primary px-3 py-2 font-semibold text-primary-foreground focus:not-sr-only focus:outline-none lg:col-span-2"
        >
          Skip to admin workspace
        </a>
        <header className="flex flex-wrap items-start justify-between gap-5 border-b border-border pb-6 lg:col-span-2">
          <div>
            <Link to="/" className="inline-flex min-h-10 items-center gap-2 text-sm font-semibold text-muted-foreground hover:text-primary">
              <ArrowLeft className="size-3.5" aria-hidden="true" />
              Citizen experience
            </Link>
            <p className="mt-6 text-sm font-semibold text-primary">Sahaayak operations</p>
            <h1 id="admin-title" className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">Platform control center</h1>
            <p className="mt-3 max-w-2xl text-base leading-6 text-muted-foreground">
              Observe reliability, quality, provider spend, content provenance, and workforce actions from one redacted-by-default surface.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Badge variant="outline" className="border-primary/30 bg-secondary text-secondary-foreground">
              <ShieldCheck className="size-3" aria-hidden="true" />
              {meQuery.data.role} · {meQuery.data.auth_source === "oidc" && meQuery.data.mfa_verified ? "MFA" : "local"}
            </Badge>
            <Button variant="ghost" onClick={() => { clearToken(); if (oidcConfigured) beginAdminOidcLogout(idToken); }} aria-label="End admin session">
              <LogOut className="size-3.5" aria-hidden="true" />
              Sign out
            </Button>
          </div>
        </header>

        <div className="lg:hidden">
          <details className="rounded-lg border border-border bg-card shadow-sm">
            <summary className="flex min-h-12 cursor-pointer items-center px-4 text-sm font-bold">Admin sections</summary>
            <div className="border-t border-border p-2">
              <AdminNavigation activeView={activeView} />
            </div>
          </details>
        </div>

        <aside className="hidden lg:block" aria-label="Admin navigation">
          <AdminNavigation activeView={activeView} />
        </aside>

        <section id="admin-content" tabIndex={-1} className="min-w-0 scroll-mt-6 outline-none" aria-label="Admin workspace">
          {children}
        </section>

        <footer className="border-t border-border py-5 text-sm text-muted-foreground lg:col-span-2">
          <div className="flex flex-wrap justify-between gap-3">
            <span>Admin telemetry is redacted by default. Elevated access must be separately authorized and audited.</span>
            <span>Actor · {meQuery.data.actor_id}</span>
          </div>
        </footer>
      </div>
    </main>
  );
}

function AdminNavigation({ activeView }: { activeView: AdminView }) {
  return (
    <nav aria-label="Admin sections">
      <ul className="grid gap-1">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const active = item.view === activeView;
          return (
            <li key={item.view}>
              <Link
                to={item.href}
                aria-current={active ? "page" : undefined}
                className={`flex min-h-11 items-center gap-3 rounded-lg border-l-4 px-3 text-sm font-semibold transition-colors ${
                  active
                    ? "border-primary bg-secondary text-primary"
                    : "border-transparent text-muted-foreground hover:bg-muted hover:text-foreground"
                }`}
              >
                <Icon className="size-4" aria-hidden="true" />
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

function AdminAccessGate({ onToken, error, onClear, oidcConfigured }: { onToken: (token: string) => void; error?: string; onClear?: () => void; oidcConfigured: boolean }) {
  const [draft, setDraft] = useState("");
  const [oidcError, setOidcError] = useState<string | null>(null);
  const allowManualToken = !oidcConfigured || import.meta.env.VITE_ADMIN_ALLOW_MANUAL_TOKEN === "true";
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (draft.trim()) onToken(draft);
  };

  return (
    <main className="grid min-h-svh place-items-center bg-background px-5 text-foreground" aria-labelledby="admin-access-title">
      <Card className="w-full max-w-lg border-border bg-card shadow-sm">
        <CardContent className="space-y-6 p-6 sm:p-8">
          <div>
            <p className="text-sm font-semibold text-primary">Workforce access</p>
            <h1 id="admin-access-title" className="mt-3 text-3xl font-bold">Platform control center</h1>
            <p className="mt-3 text-base leading-6 text-muted-foreground">
              {oidcConfigured
                ? "Use the organization identity provider. Sahaayak requires a workforce role and MFA assurance before showing platform data."
                : "Enter the deployment’s admin bearer token. It is kept in this browser tab’s session storage and is never displayed back to the page."}
            </p>
          </div>
          {error && <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">{error}</p>}
          {oidcConfigured && (
            <div className="space-y-3">
              <Button
                type="button"
                className="w-full bg-primary text-primary-foreground hover:bg-primary/90"
                onClick={() => { setOidcError(null); void beginAdminOidcLogin().catch((reason: unknown) => setOidcError(reason instanceof Error ? reason.message : "Could not start admin sign-in.")); }}
              >
                Sign in with organization SSO
              </Button>
              {oidcError && <p role="alert" className="text-sm text-destructive">{oidcError}</p>}
            </div>
          )}
          {allowManualToken && <form className="space-y-3" onSubmit={submit} aria-label="Admin sign in">
            <label className="grid gap-2 text-sm font-semibold" htmlFor="admin-token">
              Admin token
              <input
                id="admin-token"
                type="password"
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                autoComplete="off"
                className="h-11 rounded border border-border bg-background px-3 text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </label>
            <Button type="submit" className="w-full bg-primary text-primary-foreground hover:bg-primary/90">Continue securely</Button>
          </form>}
          <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground">
            <Link to="/" className="inline-flex min-h-10 items-center gap-2 hover:text-primary"><ArrowLeft className="size-3.5" aria-hidden="true" />Return to citizen app</Link>
            {onClear && <button type="button" onClick={onClear} className="min-h-10 underline underline-offset-4 hover:text-foreground">Clear rejected session</button>}
          </div>
        </CardContent>
      </Card>
    </main>
  );
}

function AdminLoading() {
  return <main className="grid min-h-svh place-items-center bg-background text-foreground"><p role="status" className="text-sm text-muted-foreground">Checking workforce access…</p></main>;
}
