import { Component, type ErrorInfo, type ReactNode } from "react";

import { Button } from "@/components/ui/button";

type AppErrorBoundaryProps = {
  children: ReactNode;
};

type AppErrorBoundaryState = {
  failed: boolean;
};

/**
 * A route failure must never leave citizens or operators with an unexplained
 * blank page. Technical details stay in the local console while the visible
 * recovery surface remains safe to show during a demo.
 */
export class AppErrorBoundary extends Component<AppErrorBoundaryProps, AppErrorBoundaryState> {
  state: AppErrorBoundaryState = { failed: false };

  static getDerivedStateFromError(): AppErrorBoundaryState {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("route_render_failed", error, info.componentStack);
  }

  render() {
    if (!this.state.failed) return this.props.children;

    return (
      <main className="grid min-h-svh place-items-center bg-background px-5 text-center text-foreground">
        <div className="max-w-lg rounded-xl border border-border bg-card p-6 shadow-sm sm:p-8">
          <p className="text-sm font-semibold text-destructive">This screen could not be displayed.</p>
          <h1 className="mt-3 text-2xl font-bold">Your work is still safe.</h1>
          <p className="mt-3 text-sm leading-6 text-muted-foreground">
            Reload this screen and try again. If the problem continues, return to the home page and use text assistance.
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <Button type="button" onClick={() => window.location.reload()}>Reload screen</Button>
            <Button type="button" variant="outline" onClick={() => window.location.assign("/")}>Return home</Button>
          </div>
        </div>
      </main>
    );
  }
}
