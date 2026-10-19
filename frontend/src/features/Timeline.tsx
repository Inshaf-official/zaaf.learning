import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import { useSession } from "../store";
import { indianDate } from "../lib/student-forms";
import type { Page } from "../types";
import { Loading, ErrorState } from "../App";
import EntityForm from "./EntityForm";
interface Entry {
  id: string;
  date: string;
  kind: string;
  text: string;
}
export default function Timeline({
  studentId,
  canManage,
}: {
  studentId: number;
  canManage: boolean;
}) {
  const { t } = useTranslation();
  const member = useSession((s) => s.membership);
  const client = useQueryClient();
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");
  const [adding, setAdding] = useState(false);
  const query = useQuery({
    queryKey: ["timeline", member?.id, studentId, page],
    queryFn: () =>
      api<Page<Entry>>(`/students/${studentId}/timeline/?page=${page}`),
  });
  return (
    <section className="panel">
      <h2>{t("timeline")}</h2>
      {canManage && (
        <button onClick={() => setAdding(!adding)}>{t("addRemark")}</button>
      )}
      {adding && (
        <EntityForm
          fields={[
            {
              name: "kind",
              label: t("kind"),
              type: "select",
              required: true,
              options: ["REMARK", "INCIDENT", "FEE_NOTE"].map((value) => ({
                value,
                label: t(value.toLowerCase()),
              })),
            },
            {
              name: "text",
              label: t("note"),
              type: "textarea",
              required: true,
            },
            {
              name: "visible_to_family",
              label: t("visibleToFamily"),
              type: "checkbox",
            },
          ]}
          onSubmit={async (data) => {
            try {
              await api("/timeline-entries/", {
                method: "POST",
                body: { ...data, student: studentId },
              });
              setAdding(false);
              await client.invalidateQueries({ queryKey: ["timeline"] });
            } catch (e) {
              setError(String(e));
            }
          }}
        />
      )}
      {query.isPending ? (
        <Loading />
      ) : query.error ? (
        <ErrorState error={query.error} retry={() => void query.refetch()} />
      ) : (
        <>
          <ol className="timeline-list">
            {query.data.results.map((entry) => (
              <li key={entry.id}>
                <small>
                  {indianDate(entry.date)} · {t(entry.kind.toLowerCase())}
                </small>
                <p>{entry.text}</p>
              </li>
            ))}
          </ol>
          {!query.data.count && <p>{t("noTimeline")}</p>}
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
        </>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
