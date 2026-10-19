import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Bell } from "lucide-react";
import { api } from "../api";
import { useSession } from "../store";
import { Loading, ErrorState } from "../App";
import { indianDate } from "../lib/student-forms";
import type { Notification, Page } from "../types";
export default function MedicalAlerts() {
  const { t } = useTranslation();
  const member = useSession((s) => s.membership);
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");
  const client = useQueryClient();
  const key = ["notifications", member?.id, page];
  const query = useQuery({
    queryKey: key,
    queryFn: () => api<Page<Notification>>(`/notifications/?page=${page}`),
    refetchInterval: 30_000,
  });
  async function markRead(notification: Notification) {
    const old = client.getQueryData<Page<Notification>>(key);
    client.setQueryData<Page<Notification>>(key, (data) =>
      data
        ? {
            ...data,
            results: data.results.map((value) =>
              value.id === notification.id
                ? { ...value, read_at: new Date().toISOString() }
                : value,
            ),
          }
        : data,
    );
    try {
      await api(`/notifications/${notification.id}/read/`, { method: "POST" });
    } catch (e) {
      client.setQueryData(key, old);
      setError(e instanceof Error ? e.message : t("retry"));
    }
  }
  return (
    <section className="panel medical-alerts">
      <h2>
        <Bell size={20} />
        {t("medicalAlerts")}
      </h2>
      {query.isPending ? (
        <Loading />
      ) : query.error ? (
        <ErrorState error={query.error} retry={() => void query.refetch()} />
      ) : (
        <>
          {query.data.results.length ? (
            <ul className="alert-list">
              {query.data.results.map((notification) => (
                <li
                  key={notification.id}
                  className={notification.read_at ? "" : "unread"}
                >
                  <strong>{t("emergencyAccessAlert")}</strong>
                  <p>{notification.body}</p>
                  <small>{indianDate(notification.created_at)}</small>
                  <div className="row-actions">
                    {notification.student && (
                      <Link to={`/students/${notification.student}`}>
                        {t("viewStudent")}
                      </Link>
                    )}
                    {!notification.read_at && (
                      <button onClick={() => void markRead(notification)}>
                        {t("markRead")}
                      </button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">{t("noMedicalAlerts")}</p>
          )}
          {query.data.count > 25 && (
            <div className="pagination">
              <button
                disabled={!query.data.previous}
                onClick={() => setPage(page - 1)}
              >
                {t("previous")}
              </button>
              <button
                disabled={!query.data.next}
                onClick={() => setPage(page + 1)}
              >
                {t("next")}
              </button>
            </div>
          )}
        </>
      )}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
    </section>
  );
}
