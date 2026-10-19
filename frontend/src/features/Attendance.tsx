import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api, download, ApiError } from "../api";
import { useSession } from "../store";
import { useOptions, allPages, localToday } from "../lib/student-forms";
import type { ClassGroup } from "../lib/student-forms";
import type { Student, Page } from "../types";
import { pending, replay, storePending, discard } from "../lib/offline";
import type { PendingSave } from "../lib/offline";
import { Loading, ErrorState } from "../App";
import Roster from "./Roster";
interface Record {
  id: number;
  student: number;
  status: "PRESENT" | "ABSENT" | "LATE";
  revision: number;
}
interface Summary {
  student: number;
  name: string;
  total: number;
  attended: number;
  percentage: number;
  alert: boolean;
}
export default function Attendance() {
  const { t } = useTranslation();
  const member = useSession((s) => s.membership);
  const groups = useOptions<ClassGroup>("class-groups");
  const [group, setGroup] = useState("");
  const [date, setDate] = useState(localToday());
  const [session, setSession] = useState("DAY");
  const [statuses, setStatuses] = useState<{ [id: number]: Record["status"] }>(
    {},
  );
  const [queue, setQueue] = useState<PendingSave[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [start, setStart] = useState(localToday().slice(0, 8) + "01");
  const canMark = member?.role === "ADMIN" || member?.role === "TEACHER";
  const roster = useQuery({
    queryKey: ["register", member?.id, group, date, session],
    enabled: !!group && canMark,
    queryFn: async () => ({
      students: await allPages<Student>(`/students/?class_group=${group}`),
      records: await allPages<Record>(
        `/attendance/?student__class_group=${group}&date=${date}&session=${encodeURIComponent(session)}`,
      ),
    }),
  });
  const reports = useQuery({
    queryKey: ["attendance-summary", member?.id, group, start, date],
    queryFn: () =>
      api<Page<Summary>>(
        `/attendance/summary/?start=${start}&end=${date}${group ? "&class_group=" + group : ""}`,
      ),
  });
  useEffect(() => {
    if (roster.data)
      setStatuses(
        Object.fromEntries(
          roster.data.students.map((s) => [
            s.id,
            roster.data.records.find((r) => r.student === s.id)?.status ||
              "PRESENT",
          ]),
        ),
      );
  }, [roster.data]);
  useEffect(() => {
    if (!member) return;
    const refresh = () => void pending(member.id).then(setQueue);
    const sync = () => {
      void replay(member.id).then(() => {
        refresh();
        if (group) void roster.refetch();
        void reports.refetch();
      });
    };
    refresh();
    if (navigator.onLine) sync();
    window.addEventListener("online", sync);
    return () => window.removeEventListener("online", sync);
  }, [member?.id, group]);
  async function save() {
    if (!member || !roster.data) return;
    setBusy(true);
    setError("");
    setMessage("");
    const body = {
      date,
      session,
      rows: roster.data.students.map((s) => ({
        student: s.id,
        status: statuses[s.id] || "PRESENT",
        revision:
          roster.data.records.find((r) => r.student === s.id)?.revision || 0,
      })),
    };
    try {
      await api("/attendance/bulk/", { method: "POST", body });
      setMessage(t("saved"));
      await roster.refetch();
      await reports.refetch();
    } catch (e) {
      if (!(e instanceof ApiError)) {
        await storePending({
          id: crypto.randomUUID(),
          membership: member.id,
          path: "/attendance/bulk/",
          body,
          created: new Date().toISOString(),
        });
        setQueue(await pending(member.id));
        setMessage(t("queued"));
      } else setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  const count = (status: Record["status"]) =>
    Object.values(statuses).filter((s) => s === status).length;
  return (
    <>
      <h1>{t("attendance")}</h1>
      <section className="panel">
        <div className="filter-grid">
          <label>
            {t("class")}
            <select value={group} onChange={(e) => setGroup(e.target.value)}>
              <option value="">{t("choose")}</option>
              {groups.data?.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            {t("date")}
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              max={localToday()}
            />
          </label>
          {canMark && (
            <label>
              {t("session")}
              <input
                value={session}
                onChange={(e) => setSession(e.target.value.toUpperCase())}
                maxLength={40}
              />
            </label>
          )}
        </div>
      </section>
      {queue.length > 0 && (
        <section className="panel">
          <h2>{t("pendingSaves")}</h2>
          {queue.map((item) => (
            <div key={item.id}>
              <p>{item.error || t("queued")}</p>
              <button
                onClick={() =>
                  void discard(item.id).then(() =>
                    pending(member!.id).then(setQueue),
                  )
                }
              >
                {t("discardQueued")}
              </button>
            </div>
          ))}
          <button
            onClick={() =>
              void replay(member!.id).then(() =>
                pending(member!.id).then(setQueue),
              )
            }
          >
            {t("retry")}
          </button>
        </section>
      )}
      {canMark && group && (
        <section className="panel">
          {roster.isPending ? (
            <Loading />
          ) : roster.error ? (
            <ErrorState
              error={roster.error}
              retry={() => void roster.refetch()}
            />
          ) : (
            <>
              <p className="running-count">
                {t("present")}: {count("PRESENT")} · {t("absent")}:{" "}
                {count("ABSENT")} · {t("late")}: {count("LATE")}
              </p>
              <Roster
                count={roster.data!.students.length}
                row={(index) => {
                  const student = roster.data!.students[index];
                  return (
                    <div className="attendance-row">
                      <strong>{student.name}</strong>
                      <div className="status-toggle">
                        {(["PRESENT", "ABSENT", "LATE"] as const).map(
                          (status) => (
                            <button
                              key={status}
                              aria-label={`${student.name}: ${t(status.toLowerCase())}`}
                              aria-pressed={statuses[student.id] === status}
                              disabled={!student.can_manage}
                              onClick={() =>
                                setStatuses((previous) => ({
                                  ...previous,
                                  [student.id]: status,
                                }))
                              }
                            >
                              {t(status.toLowerCase())}
                            </button>
                          ),
                        )}
                      </div>
                    </div>
                  );
                }}
              />
              <div className="sticky-action">
                <button
                  className="primary"
                  disabled={
                    busy ||
                    !roster.data!.students.length ||
                    roster.data!.students.some((s) => !s.can_manage)
                  }
                  onClick={() => void save()}
                >
                  {t("saveAttendance")}
                </button>
              </div>
            </>
          )}
        </section>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {message && <p role="status">{message}</p>}
      <section className="panel">
        <h2>{t("attendanceReports")}</h2>
        <label>
          {t("startsOn")}
          <input
            type="date"
            value={start}
            onChange={(e) => setStart(e.target.value)}
          />
        </label>
        {reports.isPending ? (
          <Loading />
        ) : reports.error ? (
          <ErrorState
            error={reports.error}
            retry={() => void reports.refetch()}
          />
        ) : (
          <ul className="people">
            {reports.data.results.map((row) => (
              <li key={row.student}>
                <strong>{row.name}</strong>
                <span>
                  {row.attended}/{row.total} · {row.percentage}%{" "}
                  {row.alert && t("lowAttendance")}
                </span>
              </li>
            ))}
          </ul>
        )}
        <div className="row-actions">
          {["csv", "pdf"].map((file) => (
            <button
              key={file}
              onClick={() =>
                void download(
                  `/attendance/export/?start=${start}&end=${date}&file=${file}${group ? "&class_group=" + group : ""}`,
                  `attendance.${file}`,
                ).catch((e) => setError(String(e)))
              }
            >
              {file.toUpperCase()}
            </button>
          ))}
        </div>
      </section>
    </>
  );
}
