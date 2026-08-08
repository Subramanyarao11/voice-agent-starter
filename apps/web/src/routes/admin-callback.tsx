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
    <main className="grid min-h-svh place-items-center bg-background px-5 text-foreground">
      <Card className="w-full max-w-lg border-border bg-card shadow-sm">
        <CardContent className="space-y-4 p-8">
          <p className="text-sm font-semibold text-primary">Workforce access</p>
          <h1 className="text-2xl font-bold">Completing secure sign-in…</h1>
          {error ? (
            <>
              <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">{error}</p>
              <Link to="/admin" className="text-sm text-primary underline underline-offset-4">Return to admin sign-in</Link>
            </>
          ) : (
            <p role="status" className="text-base text-muted-foreground">Verifying the identity-provider response.</p>
          )}
        </CardContent>
      </Card>
    </main>
  );
}
