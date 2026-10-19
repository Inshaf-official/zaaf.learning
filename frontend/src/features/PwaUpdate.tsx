import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
export default function PwaUpdate() {
  const { t } = useTranslation();
  const [waiting, setWaiting] = useState<ServiceWorker | null>(null);
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;
    let removed = false;
    void navigator.serviceWorker.ready.then((registration) => {
      if (removed) return;
      if (registration.waiting) setWaiting(registration.waiting);
      registration.addEventListener("updatefound", () => {
        const worker = registration.installing;
        worker?.addEventListener("statechange", () => {
          if (
            worker.state === "installed" &&
            navigator.serviceWorker.controller
          )
            setWaiting(worker);
        });
      });
    });
    return () => {
      removed = true;
    };
  }, []);
  if (!waiting) return null;
  return (
    <aside className="update-banner" role="status">
      <p>{t("updateAvailable")}</p>
      <button
        onClick={() => {
          navigator.serviceWorker.addEventListener(
            "controllerchange",
            () => window.location.reload(),
            { once: true },
          );
          waiting.postMessage({ type: "SKIP_WAITING" });
        }}
      >
        {t("updateApp")}
      </button>
      <button onClick={() => setWaiting(null)}>{t("later")}</button>
    </aside>
  );
}
