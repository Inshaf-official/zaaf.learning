import { readFileSync } from "node:fs";
import { defineConfig } from "vitest/config";
import tailwindcss from "@tailwindcss/vite";
import { VitePWA } from "vite-plugin-pwa";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      strategies: "injectManifest",
      srcDir: "src",
      filename: "sw.ts",
      registerType: "prompt",
      injectRegister: false,
      manifest: {
        name: "Institution office",
        short_name: "Office",
        description: "Your institution workspace",
        lang: "en-IN",
        start_url: "/",
        scope: "/",
        display: "standalone",
        theme_color: "#1F3A5F",
        background_color: "#F7F5F0",
        icons: [
          { src: "/icon-192.png", sizes: "192x192", type: "image/png" },
          {
            src: "/icon-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "any",
          },
          {
            src: "/icon-maskable.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable",
          },
        ],
      },
      injectManifest: {
        globPatterns: ["**/*.{js,css,html,png,svg,woff2}"],
        maximumFileSizeToCacheInBytes: 1024 * 1024,
        manifestTransforms: [
          async (entries) => {
            const manifest = JSON.parse(
              readFileSync("dist/.vite/manifest.json", "utf8"),
            ) as Record<string, { file: string; imports?: string[] }>;
            const shell = new Set<string>();
            function add(key: string) {
              const entry = manifest[key];
              if (!entry || shell.has(entry.file)) return;
              shell.add(entry.file);
              for (const dependency of entry.imports || []) add(dependency);
            }
            for (const key of Object.keys(manifest))
              if (
                key === "index.html" ||
                /src\/features\/(Login|Dashboard|DashboardSummary|MedicalAlerts|PwaUpdate|InstitutionLogo)\.tsx$/.test(
                  key,
                )
              )
                add(key);
            return {
              manifest: entries.filter(
                (entry) =>
                  !entry.url.endsWith(".js") ||
                  !entry.url.startsWith("assets/") ||
                  shell.has(entry.url),
              ),
              warnings: [],
            };
          },
        ],
      },
    }),
  ],
  build: { manifest: true },
  server: {
    proxy: {
      "/api": {
        target:
          (
            globalThis as unknown as {
              process: { env: Record<string, string> };
            }
          ).process.env.API_PROXY_TARGET || "http://127.0.0.1:8000",
        changeOrigin: false,
      },
    },
  },
  test: { environment: "jsdom", setupFiles: ["./src/test-setup.ts"] },
});
