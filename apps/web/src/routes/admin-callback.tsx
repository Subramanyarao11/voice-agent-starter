import { useEffect, useRef, useState } from "react";

import { Link, useNavigate } from "@tanstack/react-router";

import { Card, CardContent } from "@/components/ui/card";
import { completeAdminOidcLogin } from "@/features/admin/oidc";
import { useAdminSessionStore } from "@/features/admin/store";

export function AdminCallbackPage() {
  const navigate = useNavigate();
  const setTokens = useAdminSessionStore((state) => state.setTokens);
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    void completeAdminOidcLogin()
      .then((tokens) => {
        setTokens(tokens);
        return navigate({ to: "/admin" });
      })
      .catch((reason: unknown) => {
        setError(reason instanceof Error ? reason.message : "Admin sign-in failed.");
      });
  }, [navigate, setTokens]);

  return (
    <main className="grid min-h-svh place-items-center bg-ink px-5 text-paper">
      <Card className="w-full max-w-lg border-acid/20 bg-paper/[0.04] text-paper">
        <CardContent className="space-y-4 p-8">
          <p className="font-mono text-[0.62rem] uppercase tracking-[0.22em] text-acid">Workforce access</p>
          <h1 className="text-2xl font-extrabold">Completing secure sign-in…</h1>
          {error ? (
            <>
              <p role="alert" className="rounded-xl border border-orange/30 bg-orange/10 px-4 py-3 text-sm text-orange">{error}</p>
              <Link to="/admin" className="text-sm text-acid underline underline-offset-4">Return to admin sign-in</Link>
            </>
          ) : (
            <p role="status" className="text-sm text-paper/60">Verifying the identity-provider response.</p>
          )}
        </CardContent>
      </Card>
    </main>
  );
}
