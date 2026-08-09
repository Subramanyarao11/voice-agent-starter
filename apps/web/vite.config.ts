import path from "node:path";
import { fileURLToPath } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

const currentDirectory = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      strategies: "injectManifest",
      srcDir: "src/pwa",
      filename: "service-worker.ts",
      injectRegister: false,
      registerType: "prompt",
      manifest: false,
      devOptions: { enabled: false },
      injectManifest: {
        globPatterns: ["**/*.{js,css,html,svg,webmanifest}"],
        globIgnores: ["**/admin-*.js", "**/applications-*.js", "**/workbox-window*.js"],
        maximumFileSizeToCacheInBytes: 2 * 1024 * 1024,
      },
    }),
  ],
  resolve: {
    alias: {
      "@": path.resolve(currentDirectory, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      // The citizen voice flow uses the same /api origin over WebSocket. Vite
      // must explicitly forward upgrade requests or the browser falls back to
      // a generic connection error before the microphone can start.
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        ws: true,
      },
      "/health": "http://localhost:8000",
    },
  },
  build: {
    chunkSizeWarningLimit: 700,
  },
});
