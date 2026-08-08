import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MotionConfig } from "motion/react";
import { RouterProvider } from "@tanstack/react-router";

import "@fontsource-variable/noto-sans/wght.css";
import "@fontsource-variable/noto-sans-bengali/wght.css";
import "@fontsource-variable/noto-sans-devanagari/wght.css";
import "@fontsource-variable/noto-sans-gujarati/wght.css";
import "@fontsource-variable/noto-sans-gurmukhi/wght.css";
import "@fontsource-variable/noto-sans-kannada/wght.css";
import "@fontsource-variable/noto-sans-malayalam/wght.css";
import "@fontsource-variable/noto-sans-oriya/wght.css";
import "@fontsource-variable/noto-sans-tamil/wght.css";
import "@fontsource-variable/noto-sans-telugu/wght.css";

import { router } from "@/app/router";
import { UiProvider } from "@/features/i18n/ui-provider";
import "@/index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <MotionConfig reducedMotion="user">
        <UiProvider>
          <RouterProvider router={router} />
        </UiProvider>
      </MotionConfig>
    </QueryClientProvider>
  </StrictMode>,
);
