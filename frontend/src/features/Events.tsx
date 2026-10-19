import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import { useSession } from "../store";
import { useOptions } from "../lib/student-forms";
import type { AcademicYear, ClassGroup, Division } from "../lib/student-forms";
import type { Page } from "../types";
import { Loading, ErrorState } from "../App";
import { Sheet } from "./StudentForms";
import EntityForm from "./EntityForm";
interface Event {
  id: number;
  name: string;
  description: string;
  academic_year: number;
  starts_on: string;
}
interface Eligible {
  id: number;
  name: string;
  event_count: number;
  never_selected: boolean;
}
interface Participant {
  id: number;
  student: number;
  name: string;
  status: string;
}
export default function Events() {
  const { t } = useTranslation();
  const member = useSession((s) => s.membership);
  const admin = member?.role === "ADMIN";
  const staff = admin || member?.role === "TEACHER";
  const client = useQueryClient();
  const events = useOptions<Event>("events");
  const years = useOptions<AcademicYear>("academic-years");
  const groups = useOptions<ClassGroup>("class-groups");
  const divisions = useOptions<Division>("divisions");
  const [id, setId] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<number[]>([]);
  const [open, setOpen] = useState<"create" | "eligibility" | null>(null);
  const [error, setError] = useState("");
  const fair = useQuery({
    queryKey: ["fair", member?.id, id, page],
    enabled: !!id && staff,
    queryFn: () =>
      api<Page<Eligible>>(`/events/${id}/fair_selection/?page=${page}`),
  });
  const participants = useQuery({
    queryKey: ["participants", member?.id, id],
    enabled: !!id,
    queryFn: () => api<Page<Participant>>(`/events/${id}/participation/`),
  });
  async function mutate(path: string, body: unknown) {
    setError("");
    try {
      await api(path, { method: "POST", body });
      setOpen(null);
      setSelected([]);
      await client.invalidateQueries();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("retry"));
    }
  }
  return (
    <>
      <h1>{t("events")}</h1>
      {admin && (
        <button className="primary" onClick={() => setOpen("create")}>
          {t("createEvent")}
        </button>
      )}
      <section className="panel">
        <label>
          {t("event")}
          <select
            value={id}
            onChange={(e) => {
              setId(e.target.value);
              setPage(1);
              setSelected([]);
            }}
          >
            <option value="">{t("choose")}</option>
            {events.data?.map((event) => (
              <option key={event.id} value={event.id}>
                {event.name}
              </option>
            ))}
          </select>
        </label>
        {id && (
          <>
            <p>{events.data?.find((e) => String(e.id) === id)?.description}</p>
            {admin && (
              <button onClick={() => setOpen("eligibility")}>
                {t("addEligibility")}
              </button>
            )}
          </>
        )}
      </section>
      {id && staff && (
        <section className="panel">
          <h2>{t("fairSelection")}</h2>
          {fair.isPending ? (
            <Loading />
          ) : fair.error ? (
            <ErrorState error={fair.error} retry={() => void fair.refetch()} />
          ) : (
            <>
              <ul className="people">
                {fair.data.results.map((student) => (
                  <li
                    key={student.id}
                    className={
                      student.never_selected ? "zero-participation" : ""
                    }
                  >
                    <label className="check">
                      <input
                        type="checkbox"
                        checked={selected.includes(student.id)}
                        disabled={!admin}
                        onChange={(e) =>
                          setSelected((old) =>
                            e.target.checked
                              ? [...old, student.id]
                              : old.filter((x) => x !== student.id),
                          )
                        }
                      />
                      {student.name}
                    </label>
                    <span>
                      {t("eventsTaken")}: {student.event_count}
                      {student.never_selected
                        ? " · " + t("noPreviousEvents")
                        : ""}
                    </span>
                  </li>
                ))}
              </ul>
              <div className="pagination">
                <button
                  disabled={!fair.data.previous}
                  onClick={() => setPage(page - 1)}
                >
                  {t("previous")}
                </button>
                <button
                  disabled={!fair.data.next}
                  onClick={() => setPage(page + 1)}
                >
                  {t("next")}
                </button>
              </div>
              {admin && (
                <div className="row-actions">
                  {["SELECTED", "PARTICIPATED"].map((status) => (
                    <button
                      key={status}
                      disabled={!selected.length}
                      onClick={() =>
                        void mutate(`/events/${id}/select/`, {
                          students: selected,
                          status,
                        })
                      }
                    >
                      {t(
                        status === "SELECTED"
                          ? "selectParticipants"
                          : "recordParticipation",
                      )}
                    </button>
                  ))}
                </div>
              )}
            </>
          )}
        </section>
      )}
      {id && participants.data && (
        <section className="panel">
          <h2>{t("participants")}</h2>
          <ul className="people">
            {participants.data.results.map((p) => (
              <li key={p.id}>
                <strong>{p.name}</strong>
                <span>{t(p.status.toLowerCase())}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <Sheet
        open={!!open}
        onOpenChange={() => setOpen(null)}
        title={t(open === "create" ? "createEvent" : "addEligibility")}
        description={t("eligibilityHelp")}
      >
        {open === "create" ? (
          <EntityForm
            fields={[
              { name: "name", label: t("recordName"), required: true },
              {
                name: "description",
                label: t("description"),
                type: "textarea",
              },
              {
                name: "academic_year",
                label: t("academicYear"),
                type: "select",
                required: true,
                options: years.data?.map((y) => ({
                  value: String(y.id),
                  label: y.name,
                })),
              },
              {
                name: "starts_on",
                label: t("date"),
                type: "date",
                required: true,
              },
            ]}
            onSubmit={(data) =>
              mutate("/events/", {
                ...data,
                academic_year: Number(data.academic_year),
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
              { name: "tags", label: t("interestTags") },
            ]}
            onSubmit={(data) =>
              mutate("/event-eligibility/", {
                event: Number(id),
                class_group: data.class_group ? Number(data.class_group) : null,
                division: data.division ? Number(data.division) : null,
                interest_tags: String(data.tags || "")
                  .split(",")
                  .map((x) => x.trim())
                  .filter(Boolean),
              })
            }
          />
        )}
      </Sheet>
    </>
  );
}
