import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Plus, Pencil, Trash2 } from "lucide-react";
import { api } from "../api";
import { Loading, ErrorState, useConfig } from "../App";
import { useSession } from "../store";
import { labelKey } from "../i18n";
import { useOptions, indianDate } from "../lib/student-forms";
import type {
  AcademicYear,
  ClassGroup,
  Division,
  Subject,
  Teacher,
  Assignment,
} from "../lib/student-forms";
import type { Page } from "../types";
import { Sheet } from "./StudentForms";
type Entity =
  | "academic-years"
  | "class-groups"
  | "divisions"
  | "subjects"
  | "teacher-assignments";
type Row = AcademicYear | ClassGroup | Division | Subject | Assignment;
const defaults = {
  name: "",
  starts_on: "",
  ends_on: "",
  is_current: false,
  academic_year: "",
  class_group: "",
  code: "",
  teacher: "",
  division: "",
  subject: "",
  is_class_teacher: false,
};
const baseSchema = z.object({
  name: z.string().max(100),
  starts_on: z.string(),
  ends_on: z.string(),
  is_current: z.boolean(),
  academic_year: z.string(),
  class_group: z.string(),
  code: z.string().max(30),
  teacher: z.string(),
  division: z.string(),
  subject: z.string(),
  is_class_teacher: z.boolean(),
});
type Fields = z.infer<typeof baseSchema>;
export default function AcademicSetup() {
  const { t } = useTranslation();
  const member = useSession((s) => s.membership);
  const config = useConfig();
  const client = useQueryClient();
  const [entity, setEntity] = useState<Entity>("academic-years");
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const years = useOptions<AcademicYear>("academic-years");
  const groups = useOptions<ClassGroup>("class-groups");
  const divisions = useOptions<Division>("divisions");
  const subjects = useOptions<Subject>("subjects");
  const teachers = useOptions<Teacher>("teachers");
  const list = useQuery({
    queryKey: ["academic", member?.id, entity, page],
    queryFn: () => api<Page<Row>>(`/${entity}/?page=${page}`),
  });
  const labels: Record<Entity, string> = {
    "academic-years": t("academicYears"),
    "class-groups": t(labelKey(config.data?.groups.primary || "Class")),
    divisions: t(labelKey(config.data?.groups.secondary || "Division")),
    subjects: t("subjects"),
    "teacher-assignments": t("teacherAssignments"),
  };
  const schema = baseSchema.superRefine((fields, ctx) => {
    const required = (field: keyof Fields) => {
      if (!fields[field])
        ctx.addIssue({ code: "custom", path: [field], message: t("required") });
    };
    if (entity !== "teacher-assignments") required("name");
    if (entity === "academic-years") {
      required("starts_on");
      required("ends_on");
      if (fields.starts_on > fields.ends_on)
        ctx.addIssue({
          code: "custom",
          path: ["ends_on"],
          message: t("invalidDates"),
        });
    }
    if (entity === "class-groups") required("academic_year");
    if (entity === "subjects") required("code");
    if (entity === "divisions" || entity === "teacher-assignments")
      required("class_group");
    if (entity === "teacher-assignments") {
      required("teacher");
      if (!fields.is_class_teacher) required("subject");
    }
  });
  const form = useForm<Fields>({
    resolver: zodResolver(schema),
    defaultValues: defaults,
  });
  function begin(row?: Row) {
    setError("");
    setEditing(row?.id || null);
    const values: Fields = { ...defaults };
    if (row) {
      if ("name" in row) values.name = row.name;
      if ("starts_on" in row) {
        values.starts_on = row.starts_on;
        values.ends_on = row.ends_on;
        values.is_current = row.is_current;
      }
      if ("academic_year" in row)
        values.academic_year = String(row.academic_year);
      if ("class_group" in row) values.class_group = String(row.class_group);
      if ("code" in row) values.code = row.code;
      if ("teacher" in row) {
        values.teacher = String(row.teacher);
        values.division = row.division ? String(row.division) : "";
        values.subject = row.subject ? String(row.subject) : "";
        values.is_class_teacher = row.is_class_teacher;
      }
    }
    form.reset(values);
    setOpen(true);
  }
  async function refresh() {
    await client.invalidateQueries({ queryKey: ["academic"] });
    await client.invalidateQueries({ queryKey: ["options"] });
    await client.invalidateQueries({ queryKey: ["student-capabilities"] });
    await client.invalidateQueries({ queryKey: ["students"] });
  }
  async function save(fields: Fields) {
    let body: unknown;
    switch (entity) {
      case "academic-years":
        body = {
          name: fields.name,
          starts_on: fields.starts_on,
          ends_on: fields.ends_on,
          is_current: fields.is_current,
        };
        break;
      case "class-groups":
        body = {
          name: fields.name,
          academic_year: Number(fields.academic_year),
        };
        break;
      case "divisions":
        body = { name: fields.name, class_group: Number(fields.class_group) };
        break;
      case "subjects":
        body = { name: fields.name, code: fields.code };
        break;
      case "teacher-assignments":
        body = {
          teacher: Number(fields.teacher),
          class_group: Number(fields.class_group),
          division:
            config.data?.type === "TUITION"
              ? null
              : fields.division
                ? Number(fields.division)
                : null,
          subject: fields.subject ? Number(fields.subject) : null,
          is_class_teacher: fields.is_class_teacher,
        };
        break;
    }
    setError("");
    try {
      await api(`/${entity}/${editing ? editing + "/" : ""}`, {
        method: editing ? "PATCH" : "POST",
        body,
      });
      setOpen(false);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("retry"));
    }
  }
  async function remove(row: Row) {
    if (!window.confirm(t("confirmDeleteSetup"))) return;
    setBusy(true);
    setError("");
    try {
      await api(`/${entity}/${row.id}/`, { method: "DELETE" });
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("retry"));
    } finally {
      setBusy(false);
    }
  }
  const optionError = [
    years.error,
    groups.error,
    divisions.error,
    subjects.error,
    teachers.error,
  ].find(Boolean);
  return (
    <>
      <div className="page-heading">
        <h1>{t("academicSetup")}</h1>
        <p className="muted">{t("academicSetupHelp")}</p>
      </div>
      <div className="setup-controls">
        <label>
          {t("manage")}
          <select
            value={entity}
            onChange={(e) => {
              setEntity(e.target.value as Entity);
              setPage(1);
              setError("");
            }}
          >
            {Object.entries(labels)
              .filter(
                ([key]) =>
                  key !== "divisions" || config.data?.type !== "TUITION",
              )
              .map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
          </select>
        </label>
        <button className="primary" onClick={() => begin()}>
          <Plus size={18} />
          {t("add")}
        </button>
      </div>
      {error && !open && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {optionError && (
        <ErrorState
          error={optionError}
          retry={() => void client.invalidateQueries({ queryKey: ["options"] })}
        />
      )}
      {list.isPending ? (
        <Loading />
      ) : list.error ? (
        <ErrorState error={list.error} retry={() => void list.refetch()} />
      ) : (
        <section className="panel">
          <h2>{labels[entity]}</h2>
          <ul className="people">
            {list.data.results.map((row) => (
              <li key={row.id}>
                <div>
                  <strong>{"name" in row ? row.name : row.teacher_name}</strong>
                  <span>
                    {"academic_year_name" in row
                      ? row.academic_year_name
                      : "class_group_name" in row
                        ? row.class_group_name
                        : "code" in row
                          ? row.code
                          : "starts_on" in row
                            ? `${indianDate(row.starts_on)} – ${indianDate(row.ends_on)}`
                            : ""}
                  </span>
                  {"teacher" in row && (
                    <small>
                      {row.division_name || t("wholeClass")} ·{" "}
                      {row.is_class_teacher
                        ? t("classTeacher")
                        : row.subject_name}
                    </small>
                  )}
                </div>
                <div className="row-actions">
                  <button
                    onClick={() => begin(row)}
                    aria-label={`${t("edit")} ${"name" in row ? row.name : row.teacher_name}`}
                  >
                    <Pencil size={18} />
                  </button>
                  <button
                    disabled={busy}
                    onClick={() => void remove(row)}
                    aria-label={`${t("remove")} ${"name" in row ? row.name : row.teacher_name}`}
                  >
                    <Trash2 size={18} />
                  </button>
                </div>
              </li>
            ))}
          </ul>
          {!list.data.count && <p className="notice">{t("noSetupRecords")}</p>}
          <div className="pagination">
            <button
              disabled={!list.data.previous}
              onClick={() => setPage(page - 1)}
            >
              {t("previous")}
            </button>
            <span>{page}</span>
            <button
              disabled={!list.data.next}
              onClick={() => setPage(page + 1)}
            >
              {t("next")}
            </button>
          </div>
        </section>
      )}
      <Sheet
        open={open}
        onOpenChange={setOpen}
        title={`${t(editing ? "edit" : "add")} · ${labels[entity]}`}
        description={t("setupFormHelp")}
      >
        <form onSubmit={form.handleSubmit(save)} noValidate>
          {entity !== "teacher-assignments" && (
            <label>
              {t("recordName")}
              <input {...form.register("name")} />
              <span className="field-error">
                {form.formState.errors.name?.message}
              </span>
            </label>
          )}
          {entity === "academic-years" && (
            <>
              <label>
                {t("startsOn")}
                <input type="date" {...form.register("starts_on")} />
                <span className="field-error">
                  {form.formState.errors.starts_on?.message}
                </span>
              </label>
              <label>
                {t("endsOn")}
                <input type="date" {...form.register("ends_on")} />
                <span className="field-error">
                  {form.formState.errors.ends_on?.message}
                </span>
              </label>
              <label className="check">
                <input type="checkbox" {...form.register("is_current")} />
                {t("currentYear")}
              </label>
            </>
          )}
          {entity === "class-groups" && (
            <label>
              {t("academicYear")}
              <select {...form.register("academic_year")}>
                <option value="">{t("choose")}</option>
                {years.data?.map((year) => (
                  <option key={year.id} value={year.id}>
                    {year.name}
                  </option>
                ))}
              </select>
              <span className="field-error">
                {form.formState.errors.academic_year?.message}
              </span>
            </label>
          )}
          {(entity === "divisions" || entity === "teacher-assignments") && (
            <label>
              {t(labelKey(config.data?.groups.primary || "Class"))}
              <select {...form.register("class_group")}>
                <option value="">{t("choose")}</option>
                {groups.data?.map((group) => (
                  <option key={group.id} value={group.id}>
                    {group.name} · {group.academic_year_name}
                  </option>
                ))}
              </select>
              <span className="field-error">
                {form.formState.errors.class_group?.message}
              </span>
            </label>
          )}
          {entity === "subjects" && (
            <label>
              {t("code")}
              <input {...form.register("code")} />
              <span className="field-error">
                {form.formState.errors.code?.message}
              </span>
            </label>
          )}
          {entity === "teacher-assignments" && (
            <>
              <label>
                {t(labelKey(config.data?.roles.TEACHER || "Teacher"))}
                <select {...form.register("teacher")}>
                  <option value="">{t("choose")}</option>
                  {teachers.data?.map((teacher) => (
                    <option key={teacher.user_id} value={teacher.user_id}>
                      {teacher.name}
                    </option>
                  ))}
                </select>
                <span className="field-error">
                  {form.formState.errors.teacher?.message}
                </span>
              </label>
              {config.data?.type !== "TUITION" && (
                <label>
                  {t(labelKey(config.data?.groups.secondary || "Division"))}
                  <select {...form.register("division")}>
                    <option value="">{t("wholeClass")}</option>
                    {divisions.data
                      ?.filter(
                        (division) =>
                          String(division.class_group) ===
                          form.watch("class_group"),
                      )
                      .map((division) => (
                        <option key={division.id} value={division.id}>
                          {division.name}
                        </option>
                      ))}
                  </select>
                </label>
              )}
              <label>
                {t("subject")}
                <select {...form.register("subject")}>
                  <option value="">{t("notAssigned")}</option>
                  {subjects.data?.map((subject) => (
                    <option key={subject.id} value={subject.id}>
                      {subject.name}
                    </option>
                  ))}
                </select>
                <span className="field-error">
                  {form.formState.errors.subject?.message}
                </span>
              </label>
              <label className="check">
                <input type="checkbox" {...form.register("is_class_teacher")} />
                {t("classTeacher")}
              </label>
            </>
          )}
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          <button className="primary" disabled={form.formState.isSubmitting}>
            {t("save")}
          </button>
        </form>
      </Sheet>
    </>
  );
}
