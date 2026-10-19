import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useSession } from "../store";
import { useOptions } from "../lib/student-forms";
import type { ClassGroup } from "../lib/student-forms";
import type { Page, Student } from "../types";
import { Loading, ErrorState } from "../App";
import { Sheet } from "./StudentForms";
import EntityForm from "./EntityForm";
interface Progress {
  id: number;
  student_name: string;
  date: string;
  surah: number;
  juz: number;
  lines: number;
  revision_status: string;
  note: string;
}
interface Slot {
  id: number;
  class_group_name: string;
  kind: string;
  weekday: number;
  starts_at: string;
  ends_at: string;
  label: string;
}
export default function Madrasa() {
  const { t } = useTranslation();
  const member = useSession((s) => s.membership);
  const client = useQueryClient();
  const staff = ["ADMIN", "TEACHER"].includes(member?.role || "");
  const students = useOptions<Student>("students");
  const groups = useOptions<ClassGroup>("class-groups");
  const [open, setOpen] = useState<"progress" | "timetable" | null>(null);
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");
  const progress = useQuery({
    queryKey: ["hifz", member?.id, page],
    queryFn: () => api<Page<Progress>>(`/hifz/?page=${page}`),
  });
  const timetable = useQuery({
    queryKey: ["timetable", member?.id, page],
    queryFn: () => api<Page<Slot>>(`/timetable/?page=${page}`),
  });
  const days = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
  ];
  async function submit(path: string, body: unknown) {
    try {
      await api(path, { method: "POST", body });
      setOpen(null);
      setError("");
      await client.invalidateQueries();
    } catch (e) {
      setError(String(e));
    }
  }
  return (
    <>
      <h1>{t("madrasaLearning")}</h1>
      <div className="row-actions">
        {staff && (
          <>
            <button className="primary" onClick={() => setOpen("progress")}>
              {t("recordHifz")}
            </button>
            <button onClick={() => setOpen("timetable")}>
              {t("addLesson")}
            </button>
          </>
        )}
        <Link className="call-button" to="/exams">
          {t("islamicMarks")}
        </Link>
      </div>
      <section className="panel">
        <h2>{t("hifzProgress")}</h2>
        {progress.isPending ? (
          <Loading />
        ) : progress.error ? (
          <ErrorState
            error={progress.error}
            retry={() => void progress.refetch()}
          />
        ) : (
          <ul className="people">
            {progress.data.results.map((row) => (
              <li key={row.id}>
                <strong>{row.student_name}</strong>
                <span>
                  {t("surah")} {row.surah} · {t("juz")} {row.juz} · {row.lines}{" "}
                  {t("lines")}
                </span>
                <span>{t(row.revision_status.toLowerCase())}</span>
                <small>{row.note}</small>
              </li>
            ))}
          </ul>
        )}
      </section>
      <section className="panel">
        <h2>{t("dualTimetable")}</h2>
        <ul className="people">
          {timetable.data?.results.map((slot) => (
            <li key={slot.id}>
              <strong>
                {slot.class_group_name} · {t(days[slot.weekday])}
              </strong>
              <span>
                {slot.starts_at.slice(0, 5)}–{slot.ends_at.slice(0, 5)} ·{" "}
                {slot.label} · {t(slot.kind.toLowerCase())}
              </span>
            </li>
          ))}
        </ul>
        <div className="pagination">
          <button
            disabled={!progress.data?.previous && !timetable.data?.previous}
            onClick={() => setPage(page - 1)}
          >
            {t("previous")}
          </button>
          <button
            disabled={!progress.data?.next && !timetable.data?.next}
            onClick={() => setPage(page + 1)}
          >
            {t("next")}
          </button>
        </div>
      </section>
      <Sheet
        open={!!open}
        onOpenChange={() => setOpen(null)}
        title={t(open === "progress" ? "recordHifz" : "addLesson")}
        description={t("madrasaHelp")}
      >
        {open === "progress" ? (
          <EntityForm
            fields={[
              {
                name: "student",
                label: t("student"),
                type: "select",
                required: true,
                options: students.data
                  ?.filter((s) => s.can_manage)
                  .map((s) => ({ value: String(s.id), label: s.name })),
              },
              { name: "date", label: t("date"), type: "date", required: true },
              {
                name: "surah",
                label: t("surah"),
                type: "number",
                min: 1,
                max: 114,
                required: true,
              },
              {
                name: "juz",
                label: t("juz"),
                type: "number",
                min: 1,
                max: 30,
                required: true,
              },
              {
                name: "lines",
                label: t("lines"),
                type: "number",
                min: 0,
                required: true,
              },
              {
                name: "revision_status",
                label: t("revisionStatus"),
                type: "select",
                required: true,
                options: ["NEW", "REVISING", "SECURE"].map((value) => ({
                  value,
                  label: t(value.toLowerCase()),
                })),
              },
              { name: "note", label: t("note") },
            ]}
            onSubmit={(data) =>
              submit("/hifz/", {
                ...data,
                student: Number(data.student),
                surah: Number(data.surah),
                juz: Number(data.juz),
                lines: Number(data.lines),
              })
            }
          />
        ) : (
          <EntityForm
            fields={[
              {
                name: "class_group",
                label: t("class"),
                type: "select",
                required: true,
                options: groups.data?.map((g) => ({
                  value: String(g.id),
                  label: g.name,
                })),
              },
              {
                name: "kind",
                label: t("kind"),
                type: "select",
                required: true,
                options: ["SCHOOL", "MADRASA"].map((value) => ({
                  value,
                  label: t(value.toLowerCase()),
                })),
              },
              {
                name: "weekday",
                label: t("weekday"),
                type: "select",
                required: true,
                options: days.map((day, i) => ({
                  value: String(i),
                  label: t(day),
                })),
              },
              {
                name: "starts_at",
                label: t("startsAt"),
                type: "time",
                required: true,
              },
              {
                name: "ends_at",
                label: t("endsAt"),
                type: "time",
                required: true,
              },
              { name: "label", label: t("subject"), required: true },
            ]}
            onSubmit={(data) =>
              submit("/timetable/", {
                ...data,
                class_group: Number(data.class_group),
                weekday: Number(data.weekday),
              })
            }
          />
        )}{" "}
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
      </Sheet>
    </>
  );
}
