import { createRootRoute, createRoute, createRouter, Outlet } from "@tanstack/react-router";

import { HomePage } from "@/routes/home";

function RootLayout() {
  return <Outlet />;
}

const rootRoute = createRootRoute({
  component: RootLayout,
  notFoundComponent: () => (
    <main className="grid min-h-svh place-items-center bg-ink px-6 text-center text-paper">
      <div>
        <p className="mb-2 font-mono text-xs uppercase tracking-[0.24em] text-acid">404</p>
        <h1 className="text-3xl font-extrabold">That page wandered off.</h1>
        <a className="mt-6 inline-block text-blue underline underline-offset-4" href="/">
          Return to Sahaayak
        </a>
      </div>
    </main>
  ),
});

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: HomePage,
});

const routeTree = rootRoute.addChildren([indexRoute]);

export const router = createRouter({
  routeTree,
  defaultPreload: "intent",
  scrollRestoration: true,
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
