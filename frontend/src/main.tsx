import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import "./i18n";
import "@fontsource/noto-sans-malayalam/malayalam-400.css";
import "@fontsource/noto-sans-malayalam/malayalam-600.css";
import "./styles.css";
import App from "./App";
import { queryClient } from "./lib/query";
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);

if (import.meta.env.PROD && "serviceWorker" in navigator) {
  const register = () =>
    window.setTimeout(() => {
      void navigator.serviceWorker.register("/sw.js").catch(() => {
        /* Online operation remains available when offline installation is unsupported. */
      });
    }, 3000);
  if (document.readyState === "complete") register();
  else window.addEventListener("load", register, { once: true });
}
