import { createRootRoute, createRoute, createRouter, Outlet } from "@tanstack/react-router";

import { HomePage } from "@/routes/home";
import { AdminRoutePage } from "@/routes/admin";
import { AdminCallbackPage } from "@/routes/admin-callback";
import { BenefitDetailRoutePage } from "@/routes/benefit-detail";

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

const benefitDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/benefits/$benefitId",
  component: BenefitDetailRoutePage,
});

const adminRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/admin",
  component: () => <AdminRoutePage view="overview" />,
});

const adminCallbackRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/admin/callback",
  component: AdminCallbackPage,
});

const adminOverviewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/admin/overview",
  component: () => <AdminRoutePage view="overview" />,
});

const adminConversationsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/admin/conversations",
  component: () => <AdminRoutePage view="conversations" />,
});

const adminTelemetryRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/admin/telemetry",
  component: () => <AdminRoutePage view="telemetry" />,
});

const adminEscalationsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/admin/escalations",
  component: () => <AdminRoutePage view="escalations" />,
});

const adminBenefitsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/admin/benefits",
  component: () => <AdminRoutePage view="benefits" />,
});

const adminProvidersRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/admin/providers",
  component: () => <AdminRoutePage view="providers" />,
});

const adminMessagingRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/admin/messaging",
  component: () => <AdminRoutePage view="messaging" />,
});

const adminQualityRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/admin/quality",
  component: () => <AdminRoutePage view="quality" />,
});

const adminFlagsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/admin/flags",
  component: () => <AdminRoutePage view="flags" />,
});

const adminLanguagesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/admin/languages",
  component: () => <AdminRoutePage view="languages" />,
});

const adminAuditRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/admin/audit-log",
  component: () => <AdminRoutePage view="audit" />,
});

const adminSystemRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/admin/system",
  component: () => <AdminRoutePage view="system" />,
});

const routeTree = rootRoute.addChildren([
  indexRoute,
  benefitDetailRoute,
  adminRoute,
  adminCallbackRoute,
  adminOverviewRoute,
  adminConversationsRoute,
  adminTelemetryRoute,
  adminEscalationsRoute,
  adminBenefitsRoute,
  adminProvidersRoute,
  adminMessagingRoute,
  adminQualityRoute,
  adminFlagsRoute,
  adminLanguagesRoute,
  adminAuditRoute,
  adminSystemRoute,
]);

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
