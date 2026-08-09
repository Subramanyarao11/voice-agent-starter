import { useEffect, useState } from "react";

import { useNavigate } from "@tanstack/react-router";

import { Card, CardContent } from "@/components/ui/card";
import { completeCitizenOidcLogin } from "@/features/citizen/oidc";

export function CitizenCallbackPage() {
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    void completeCitizenOidcLogin()
      .then(() => navigate({ to: "/household", replace: true }))
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Citizen sign-in failed."));
  }, [navigate]);
  return (
    <main className="grid min-h-svh place-items-center bg-background px-4 text-foreground">
      <Card className="w-full max-w-lg"><CardContent className="space-y-3 p-6"><p className="text-sm font-semibold text-primary">Citizen sign-in</p>{error ? <p role="alert" className="leading-6 text-destructive">{error}</p> : <p role="status" aria-live="polite" className="leading-6 text-muted-foreground">Finishing your secure sign-in…</p>}</CardContent></Card>
    </main>
  );
}
