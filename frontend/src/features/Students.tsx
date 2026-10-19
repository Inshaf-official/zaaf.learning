import { lazy, Suspense, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Search, Plus, ChevronRight, ShieldAlert } from "lucide-react";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import { useSession } from "../store";
import { Loading, ErrorState, useConfig } from "../App";
import { labelKey } from "../i18n";
import {
  useOptions,
  studentSchema,
  guardianSchema,
  studentPayload,
  localToday,
} from "../lib/student-forms";
import type {
  StudentFields,
  GuardianFields,
  ClassGroup,
  Division,
} from "../lib/student-forms";
import type {
  Student,
  Page,
  Capabilities,
  StudentMutation,
  Credential,
  EmergencyStudent,
} from "../types";
import {
  Sheet,
  Credentials,
  StudentInputs,
  GuardianInputs,
} from "./StudentForms";
const MedicalCard = lazy(() => import("./MedicalCard"));
export default function Students() {
  const { t } = useTranslation();
  const member = useSession((s) => s.membership);
  const config = useConfig();
  const client = useQueryClient();
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [group, setGroup] = useState("");
  const [division, setDivision] = useState("");
  const [page, setPage] = useState(1);
  const [emergency, setEmergency] = useState(false);
  const [selected, setSelected] = useState<EmergencyStudent | null>(null);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState("");
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const groups = useOptions<ClassGroup>("class-groups");
  const divisions = useOptions<Division>("divisions");
  const capabilities = useQuery({
    queryKey: ["student-capabilities", member?.id],
    queryFn: () => api<Capabilities>("/students/capabilities/"),
  });
  useEffect(() => {
    const timeout = window.setTimeout(() => {
      setDebounced(search);
      setPage(1);
    }, 300);
    return () => window.clearTimeout(timeout);
  }, [search]);
  const params = new URLSearchParams({ search: debounced, page: String(page) });
  if (group && !emergency) params.set("class_group", group);
  if (division && !emergency) params.set("division", division);
  const list = useQuery({
    queryKey: [
      "students",
      member?.id,
      debounced,
      group,
      division,
      page,
      emergency,
    ],
    queryFn: () =>
      api<Page<Student | EmergencyStudent>>(
        `/${emergency ? "medical/directory" : "students"}/?${params}`,
      ),
  });
  const form = useForm<StudentFields>({
    resolver: zodResolver(studentSchema),
    defaultValues: {
      name: "",
      admission_number: "",
      class_group: "",
      division: "",
      date_of_birth: "",
      joined_on: localToday(),
    },
  });
  const guardian = useForm<GuardianFields>({
    resolver: zodResolver(guardianSchema),
    defaultValues: {
      name: "",
      email: "",
      phone: "",
      relationship: t("parent"),
      delivery: "temporary",
    },
  });
  async function submit() {
    const validStudent = await form.trigger();
    const validGuardian = await guardian.trigger();
    if (!validStudent || !validGuardian) return;
    setError("");
    try {
      const response = await api<StudentMutation>("/students/", {
        method: "POST",
        body: {
          ...studentPayload(form.getValues()),
          guardians: [guardian.getValues()],
        },
      });
      setOpen(false);
      setCredentials(response.credentials);
      form.reset();
      guardian.reset();
      await client.invalidateQueries({ queryKey: ["students"] });
    } catch (e) {
      setError(e instanceof Error ? e.message : t("retry"));
    }
  }
  const [saving, setSaving] = useState(false);
  return (
    <>
      <div className="page-heading">
        <p className="eyebrow">{config.data?.name}</p>
        <h1>{t("students")}</h1>
        <p className="muted">{t("studentsHelp")}</p>
        {capabilities.data?.can_create && (
          <button className="primary" onClick={() => setOpen(true)}>
            <Plus size={20} />
            {t("addStudent")}
          </button>
        )}
      </div>
      <section className="student-filters">
        <label className="search-field">
          <span>{t("searchStudents")}</span>
          <div>
            <Search size={20} aria-hidden="true" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t("searchHint")}
              autoComplete="off"
            />
          </div>
        </label>
        {!emergency && (
          <div className="filter-grid">
            <label>
              {t(labelKey(config.data?.groups.primary || "Class"))}
              <select
                value={group}
                onChange={(e) => {
                  setGroup(e.target.value);
                  setDivision("");
                  setPage(1);
                }}
              >
                <option value="">{t("allGroups")}</option>
                {groups.data?.map((value) => (
                  <option key={value.id} value={value.id}>
                    {value.name} · {value.academic_year_name}
                  </option>
                ))}
              </select>
            </label>
            {config.data?.type !== "TUITION" && (
              <label>
                {t(labelKey(config.data?.groups.secondary || "Division"))}
                <select
                  value={division}
                  onChange={(e) => {
                    setDivision(e.target.value);
                    setPage(1);
                  }}
                >
                  <option value="">{t("allDivisions")}</option>
                  {divisions.data
                    ?.filter((d) => !group || String(d.class_group) === group)
                    .map((value) => (
                      <option key={value.id} value={value.id}>
                        {value.class_group_name} · {value.name}
                      </option>
                    ))}
                </select>
              </label>
            )}
          </div>
        )}
        {capabilities.data?.can_emergency_lookup && (
          <label className="check">
            <input
              type="checkbox"
              checked={emergency}
              onChange={(e) => {
                setEmergency(e.target.checked);
                setPage(1);
              }}
            />
            <ShieldAlert size={18} />
            {t("emergencySearch")}
          </label>
        )}
        {emergency && <p className="notice">{t("emergencySearchHelp")}</p>}
      </section>
      {groups.error && (
        <ErrorState error={groups.error} retry={() => void groups.refetch()} />
      )}
      {divisions.error && (
        <ErrorState
          error={divisions.error}
          retry={() => void divisions.refetch()}
        />
      )}
      {list.isPending ? (
        <Loading />
      ) : list.error ? (
        <ErrorState error={list.error} retry={() => void list.refetch()} />
      ) : (
        <section className="panel student-results">
          <p className="result-count">
            {t("studentCount", { count: list.data.count })}
          </p>
          {!list.data.results.length ? (
            <div className="empty-state">
              <Search size={28} />
              <h2>{t("noStudents")}</h2>
              <p>{t(emergency ? "emergencySearchHelp" : "noStudentsHelp")}</p>
            </div>
          ) : (
            <ul className="student-list">
              {list.data.results.map((student) => (
                <li key={student.id}>
                  {emergency ? (
                    <button
                      className="student-row"
                      onClick={() => setSelected(student)}
                    >
                      <span className="student-initial">
                        {student.name.charAt(0)}
                      </span>
                      <span>
                        <strong>{student.name}</strong>
                        <small>{student.admission_number}</small>
                      </span>
                      <ShieldAlert size={20} />
                    </button>
                  ) : (
                    <Link
                      className="student-row"
                      to={`/students/${student.id}`}
                      onMouseEnter={() =>
                        void client.prefetchQuery({
                          queryKey: ["student", member?.id, student.id],
                          queryFn: () => api(`/students/${student.id}/`),
                        })
                      }
                    >
                      <span className="student-initial">
                        {student.name.charAt(0)}
                      </span>
                      <span>
                        <strong>{student.name}</strong>
                        <small>
                          {student.admission_number}
                          {"class_group_name" in student
                            ? ` · ${student.class_group_name}${student.division_name ? "–" + student.division_name : ""}`
                            : ""}
                        </small>
                      </span>
                      <ChevronRight size={20} />
                    </Link>
                  )}
                </li>
              ))}
            </ul>
          )}
          <div className="pagination">
            <button
              disabled={!list.data.previous}
              onClick={() => setPage(page - 1)}
            >
              {t("previous")}
            </button>
            <span>{new Intl.NumberFormat("en-IN").format(page)}</span>
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
        title={t("addStudent")}
        description={t("studentCreateHelp")}
      >
        <form
          onSubmit={(event) => {
            event.preventDefault();
            setSaving(true);
            void submit().finally(() => setSaving(false));
          }}
          noValidate
        >
          <StudentInputs
            register={form.register}
            errors={form.formState.errors}
            groups={groups.data || []}
            divisions={divisions.data || []}
            selectedGroup={form.watch("class_group")}
          />
          <h3>{t("guardian")}</h3>
          <GuardianInputs
            register={guardian.register}
            errors={guardian.formState.errors}
          />
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          <button className="primary" disabled={saving}>
            {t("saveStudent")}
          </button>
        </form>
      </Sheet>
      <Credentials values={credentials} onClose={() => setCredentials([])} />
      <Sheet
        open={Boolean(selected)}
        onOpenChange={(value) => {
          if (!value) setSelected(null);
        }}
        title={selected?.name || t("medicalCard")}
        description={t("medicalPrivacy")}
      >
        {selected && (
          <Suspense fallback={<Loading />}>
            <MedicalCard key={selected.id} studentId={selected.id} />
          </Suspense>
        )}
      </Sheet>
    </>
  );
}
