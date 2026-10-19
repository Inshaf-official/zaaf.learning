import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import { useSession } from "../store";
import { useOptions, indianDate } from "../lib/student-forms";
import type { ClassGroup, Division } from "../lib/student-forms";
import type { Page, Notification } from "../types";
import { Loading, ErrorState } from "../App";
import EntityForm from "./EntityForm";
import { Sheet } from "./StudentForms";
interface Notice {
  id: number;
  title: string;
  body: string;
  created_at: string;
}
export default function Notices() {
  const { t } = useTranslation();
  const member = useSession((s) => s.membership);
  const client = useQueryClient();
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState("");
  const groups = useOptions<ClassGroup>("class-groups");
  const divisions = useOptions<Division>("divisions");
  const notices = useQuery({
    queryKey: ["notices", member?.id, page],
    queryFn: () => api<Page<Notice>>(`/notices/?page=${page}`),
  });
  const notifications = useQuery({
    queryKey: ["inbox", member?.id, page],
    queryFn: () => api<Page<Notification>>(`/notifications/?page=${page}`),
    refetchInterval: 30000,
  });
  async function markRead(id: number) {
    const key = ["inbox", member?.id, page];
    const previous = client.getQueryData<Page<Notification>>(key);
    client.setQueryData<Page<Notification>>(key, (data) =>
      data
        ? {
            ...data,
            results: data.results.map((n) =>
              n.id === id ? { ...n, read_at: new Date().toISOString() } : n,
            ),
          }
        : data,
    );
    try {
      await api(`/notifications/${id}/read/`, { method: "POST" });
    } catch (e) {
      client.setQueryData(key, previous);
      setError(String(e));
    }
  }
  return (
    <>
      <h1>{t("notices")}</h1>
      {["ADMIN", "TEACHER"].includes(member?.role || "") && (
        <button className="primary" onClick={() => setOpen(true)}>
          {t("sendNotice")}
        </button>
      )}
      <section className="panel">
        <h2>{t("notices")}</h2>
        {notices.isPending ? (
          <Loading />
        ) : notices.error ? (
          <ErrorState
            error={notices.error}
            retry={() => void notices.refetch()}
          />
        ) : (
          <>
            {notices.data.results.map((n) => (
              <article className="notice-item" key={n.id}>
                <h3>{n.title}</h3>
                <small>{indianDate(n.created_at)}</small>
                <p>{n.body}</p>
                <a
                  target="_blank"
                  rel="noopener noreferrer"
                  href={`https://wa.me/?text=${encodeURIComponent(n.title + "\n" + n.body)}`}
                >
                  {t("shareWhatsApp")}
                </a>
              </article>
            ))}
            {!notices.data.count && <p>{t("noNotices")}</p>}
            <div className="pagination">
              <button
                disabled={!notices.data.previous}
                onClick={() => setPage(page - 1)}
              >
                {t("previous")}
              </button>
              <button
                disabled={!notices.data.next}
                onClick={() => setPage(page + 1)}
              >
                {t("next")}
              </button>
            </div>
          </>
        )}
      </section>
      <section className="panel">
        <h2>{t("notifications")}</h2>
        {notifications.data?.results.map((n) => (
          <article className="notice-item" key={n.id}>
            <h3>{n.title}</h3>
            <p>{n.body}</p>
            {!n.read_at && (
              <button onClick={() => void markRead(n.id)}>
                {t("markRead")}
              </button>
            )}
          </article>
        ))}
      </section>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <Sheet
        open={open}
        onOpenChange={setOpen}
        title={t("sendNotice")}
        description={t("noticeHelp")}
      >
        <EntityForm
          fields={[
            { name: "title", label: t("title"), required: true },
            {
              name: "body",
              label: t("message"),
              type: "textarea",
              required: true,
            },
            {
              name: "audience",
              label: t("audience"),
              type: "select",
              required: true,
              options: (member?.role === "ADMIN"
                ? ["ALL", "CLASS", "DIVISION", "BATCH"]
                : ["CLASS", "DIVISION", "BATCH"]
              ).map((value) => ({ value, label: t(value.toLowerCase()) })),
            },
            {
              name: "class_group",
              label: t("class"),
              type: "select",
              options: groups.data?.map((g) => ({
                value: String(g.id),
                label: g.name,
              })),
            },
            {
              name: "division",
              label: t("division"),
              type: "select",
              options: divisions.data?.map((d) => ({
                value: String(d.id),
                label: d.class_group_name + " " + d.name,
              })),
            },
          ]}
          onSubmit={async (data) => {
            try {
              await api("/notices/", {
                method: "POST",
                body: {
                  ...data,
                  class_group: data.class_group
                    ? Number(data.class_group)
                    : null,
                  division: data.division ? Number(data.division) : null,
                },
              });
              setOpen(false);
              await client.invalidateQueries({ queryKey: ["notices"] });
            } catch (e) {
              setError(String(e));
            }
          }}
        />
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
      </Sheet>
    </>
  );
}
