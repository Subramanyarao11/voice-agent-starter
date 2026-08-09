import { createRootRoute, createRoute, createRouter, lazyRouteComponent, Outlet } from "@tanstack/react-router";

import { HomePage } from "@/routes/home";
import { AdminCallbackPage } from "@/routes/admin-callback";

const AdminRoutePage = lazyRouteComponent(() => import("@/routes/admin"), "AdminRoutePage");
const BenefitDetailRoutePage = lazyRouteComponent(
  () => import("@/routes/benefit-detail"),
  "BenefitDetailRoutePage",
);
const ApplicationsRoutePage = lazyRouteComponent(
  () => import("@/routes/applications"),
  "ApplicationsRoutePage",
);
const ApplicationDetailRoutePage = lazyRouteComponent(
  () => import("@/routes/applications"),
  "ApplicationDetailRoutePage",
);

function RootLayout() {
  return <Outlet />;
}

const rootRoute = createRootRoute({
  component: RootLayout,
  notFoundComponent: () => (
    <main className="grid min-h-svh place-items-center bg-background px-6 text-center text-foreground">
      <div>
        <p className="mb-2 text-sm font-semibold text-primary">404</p>
        <h1 className="text-3xl font-bold">That page wandered off.</h1>
        <a className="mt-6 inline-block text-primary underline underline-offset-4" href="/">
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

const applicationsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/applications",
  component: ApplicationsRoutePage,
});

const applicationDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/applications/$applicationId",
  component: ApplicationDetailRoutePage,
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

const adminDirectoryRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/admin/directory",
  component: () => <AdminRoutePage view="directory" />,
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
  applicationsRoute,
  applicationDetailRoute,
  adminRoute,
  adminCallbackRoute,
  adminOverviewRoute,
  adminConversationsRoute,
  adminTelemetryRoute,
  adminEscalationsRoute,
  adminDirectoryRoute,
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
