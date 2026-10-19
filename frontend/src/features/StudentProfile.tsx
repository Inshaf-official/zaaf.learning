import { lazy, Suspense, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, Phone, ShieldPlus, UserRound, Plus } from "lucide-react";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import { useSession } from "../store";
import { Loading, ErrorState } from "../App";
import {
  useOptions,
  studentSchema,
  guardianSchema,
  studentPayload,
  indianDate,
  localToday,
} from "../lib/student-forms";
import type {
  ClassGroup,
  Division,
  StudentFields,
  GuardianFields,
} from "../lib/student-forms";
import type { StudentDetail, Credential } from "../types";
import EntityForm from "./EntityForm";
import {
  Sheet,
  Credentials,
  StudentInputs,
  GuardianInputs,
} from "./StudentForms";
const ProfileInsights = lazy(() => import("./ProfileInsights"));
const Timeline = lazy(() => import("./Timeline"));
const MedicalCard = lazy(() => import("./MedicalCard"));
const loginSchema = z
  .object({
    identity: z.string().min(3),
    mode: z.enum(["login_id", "email"]),
    delivery: z.enum(["temporary", "email"]),
  })
  .superRefine((data, ctx) => {
    if (
      data.mode === "email" &&
      !z.string().email().safeParse(data.identity).success
    )
      ctx.addIssue({
        code: "custom",
        path: ["identity"],
        message: "Invalid email",
      });
    if (
      data.mode === "login_id" &&
      !/^[a-zA-Z0-9_-]{3,100}$/.test(data.identity)
    )
      ctx.addIssue({
        code: "custom",
        path: ["identity"],
        message: "Invalid login ID",
      });
  });
type LoginFields = z.infer<typeof loginSchema>;
export default function StudentProfile() {
  const { t } = useTranslation();
  const { id } = useParams();
  const studentId = Number(id);
  const member = useSession((s) => s.membership);
  const client = useQueryClient();
  const navigate = useNavigate();
  const student = useQuery({
    queryKey: ["student", member?.id, studentId],
    queryFn: () => api<StudentDetail>(`/students/${studentId}/`),
  });
  const groups = useOptions<ClassGroup>("class-groups");
  const divisions = useOptions<Division>("divisions");
  const [tab, setTab] = useState<"profile" | "medical" | "timeline">("profile");
  const [interestsOpen, setInterestsOpen] = useState(false);
  const [edit, setEdit] = useState(false);
  const [addGuardian, setAddGuardian] = useState(false);
  const [loginOpen, setLoginOpen] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [confirmation, setConfirmation] = useState("");
  const form = useForm<StudentFields>({ resolver: zodResolver(studentSchema) });
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
  const login = useForm<LoginFields>({
    resolver: zodResolver(loginSchema),
    defaultValues: { identity: "", mode: "login_id", delivery: "temporary" },
  });
  useEffect(() => {
    setTab("profile");
    setEdit(false);
    setError("");
  }, [studentId, member?.id]);
  async function refresh() {
    await client.invalidateQueries({
      queryKey: ["student", member?.id, studentId],
    });
    await client.invalidateQueries({ queryKey: ["students"] });
  }
  async function save(fields: StudentFields) {
    setError("");
    try {
      await api(`/students/${studentId}/`, {
        method: "PATCH",
        body: studentPayload(fields),
      });
      setEdit(false);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("retry"));
    }
  }
  async function inviteParent(fields: GuardianFields) {
    setError("");
    try {
      const data = await api<Credential>(`/students/${studentId}/guardians/`, {
        method: "POST",
        body: fields,
      });
      setAddGuardian(false);
      guardian.reset();
      if (data.temporary_password) setCredentials([data]);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("retry"));
    }
  }
  async function createLogin(fields: LoginFields) {
    setError("");
    try {
      const data = await api<Credential>(`/students/${studentId}/account/`, {
        method: "POST",
        body: {
          [fields.mode]: fields.identity,
          delivery: fields.mode === "login_id" ? "temporary" : fields.delivery,
        },
      });
      setLoginOpen(false);
      login.reset();
      setCredentials([data]);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("retry"));
    }
  }
  async function removeGuardian(linkId: number) {
    if (!window.confirm(t("confirmUnlink"))) return;
    setBusy(true);
    setError("");
    try {
      await api(`/students/${studentId}/guardians/${linkId}/`, {
        method: "DELETE",
      });
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("retry"));
    } finally {
      setBusy(false);
    }
  }
  async function archive(hard = false) {
    if (!hard && !window.confirm(t("confirmArchive"))) return;
    setBusy(true);
    setError("");
    try {
      await api(`/students/${studentId}/${hard ? "hard-delete/" : ""}`, {
        method: hard ? "POST" : "DELETE",
        body: hard ? { confirm_admission_number: confirmation } : undefined,
      });
      await client.invalidateQueries({ queryKey: ["students"] });
      client.removeQueries({ queryKey: ["student", member?.id, studentId] });
      navigate("/students");
    } catch (e) {
      setError(e instanceof Error ? e.message : t("retry"));
    } finally {
      setBusy(false);
    }
  }
  if (student.isPending) return <Loading />;
  if (student.error)
    return (
      <ErrorState error={student.error} retry={() => void student.refetch()} />
    );
  const data = student.data;
  return (
    <>
      <Link className="back-link" to="/students">
        <ArrowLeft size={18} />
        {t("students")}
      </Link>
      <header className="profile-heading">
        <span className="student-initial large">{data.name.charAt(0)}</span>
        <div>
          <p className="eyebrow">{data.admission_number}</p>
          <h1>{data.name}</h1>
          <p>
            {data.class_group_name}
            {data.division_name ? "–" + data.division_name : ""} ·{" "}
            {data.academic_year_name}
          </p>
        </div>
      </header>
      <div
        className="profile-tabs"
        role="tablist"
        aria-label={t("studentProfile")}
      >
        <button
          role="tab"
          aria-selected={tab === "profile"}
          onClick={() => setTab("profile")}
        >
          <UserRound size={18} />
          <span>{t("profile")}</span>
        </button>
        {(member?.role === "ADMIN" || member?.role === "TEACHER") && (
          <button
            role="tab"
            aria-selected={tab === "medical"}
            onClick={() => setTab("medical")}
          >
            <ShieldPlus size={18} />
            <span>{t("medicalCard")}</span>
          </button>
        )}
        <button
          role="tab"
          aria-selected={tab === "timeline"}
          onClick={() => setTab("timeline")}
        >
          {t("timeline")}
        </button>
      </div>
      {tab === "medical" ? (
        <Suspense fallback={<Loading />}>
          <MedicalCard
            key={`${member?.id}-${studentId}`}
            studentId={studentId}
          />
        </Suspense>
      ) : tab === "timeline" ? (
        <Suspense fallback={<Loading />}>
          <Timeline studentId={studentId} canManage={data.can_manage} />
        </Suspense>
      ) : (
        <>
          <Suspense fallback={<Loading />}>
            <ProfileInsights studentId={studentId} />
          </Suspense>
          <section className="panel">
            <div className="section-heading">
              <h2>{t("studentDetails")}</h2>
              {data.can_manage && (
                <button
                  onClick={() => {
                    form.reset({
                      name: data.name,
                      admission_number: data.admission_number,
                      class_group: String(data.class_group),
                      division: data.division ? String(data.division) : "",
                      date_of_birth: data.date_of_birth || "",
                      joined_on: data.joined_on || localToday(),
                    });
                    setError("");
                    setEdit(true);
                  }}
                >
                  {t("edit")}
                </button>
              )}
            </div>
            <dl className="details">
              <dt>{t("admissionNumber")}</dt>
              <dd>{data.admission_number}</dd>
              {data.date_of_birth !== undefined && (
                <>
                  <dt>{t("dateOfBirth")}</dt>
                  <dd>
                    {data.date_of_birth
                      ? indianDate(data.date_of_birth)
                      : t("notRecorded")}
                  </dd>
                </>
              )}
              <dt>{t("joinedOn")}</dt>
              <dd>{indianDate(data.joined_on)}</dd>
              <dt>{t("academicYear")}</dt>
              <dd>{data.academic_year_name}</dd>
            </dl>
          </section>
          {data.can_view_guardians && (
            <section className="panel">
              <div className="section-heading">
                <h2>{t("guardians")}</h2>
                {data.can_manage && (
                  <button
                    onClick={() => {
                      setError("");
                      setAddGuardian(true);
                    }}
                  >
                    <Plus size={18} />
                    {t("addGuardian")}
                  </button>
                )}
              </div>
              {data.guardians?.map((value) => (
                <article className="guardian-row" key={value.id}>
                  <div>
                    <strong>{value.name}</strong>
                    <span>{value.relationship}</span>
                    <span>{value.email}</span>
                  </div>
                  <div className="row-actions">
                    {value.phone && (
                      <a
                        className="call-button"
                        href={`tel:${value.phone.replace(/[^+0-9]/g, "")}`}
                      >
                        <Phone size={16} />
                        {value.phone}
                      </a>
                    )}
                    {data.can_manage && (
                      <button
                        disabled={busy || (data.guardians?.length || 0) <= 1}
                        onClick={() => void removeGuardian(value.id)}
                      >
                        {t("unlink")}
                      </button>
                    )}
                  </div>
                </article>
              ))}
            </section>
          )}
          {data.can_manage && (
            <section className="panel">
              <h2>{t("recordActions")}</h2>
              <div className="row-actions">
                <button onClick={() => setInterestsOpen(true)}>
                  {t("editInterests")}
                </button>
                {member?.type === "SCHOOL" && !data.has_login && (
                  <button
                    onClick={() => {
                      setError("");
                      setLoginOpen(true);
                    }}
                  >
                    {t("createStudentLogin")}
                  </button>
                )}
                <button disabled={busy} onClick={() => void archive()}>
                  {t("archiveStudent")}
                </button>
                {member?.role === "ADMIN" && (
                  <button
                    className="danger-outline"
                    disabled={busy}
                    onClick={() => {
                      setConfirmation("");
                      setDeleteOpen(true);
                    }}
                  >
                    {t("deletePermanently")}
                  </button>
                )}
              </div>
            </section>
          )}
        </>
      )}
      {error && !edit && !addGuardian && !loginOpen && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <Sheet
        open={edit}
        onOpenChange={setEdit}
        title={t("editStudent")}
        description={t("studentEditHelp")}
      >
        <form onSubmit={form.handleSubmit(save)} noValidate>
          <StudentInputs
            register={form.register}
            errors={form.formState.errors}
            groups={groups.data || []}
            divisions={divisions.data || []}
            selectedGroup={form.watch("class_group")}
          />
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          <button className="primary" disabled={form.formState.isSubmitting}>
            {t("saveStudent")}
          </button>
        </form>
      </Sheet>
      <Sheet
        open={addGuardian}
        onOpenChange={setAddGuardian}
        title={t("addGuardian")}
        description={t("guardianHelp")}
      >
        <form onSubmit={guardian.handleSubmit(inviteParent)} noValidate>
          <GuardianInputs
            register={guardian.register}
            errors={guardian.formState.errors}
          />
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          <button
            className="primary"
            disabled={guardian.formState.isSubmitting}
          >
            {t("inviteAction")}
          </button>
        </form>
      </Sheet>
      <Sheet
        open={loginOpen}
        onOpenChange={setLoginOpen}
        title={t("createStudentLogin")}
        description={t("studentLoginHelp")}
      >
        <form onSubmit={login.handleSubmit(createLogin)} noValidate>
          <label>
            {t("identityType")}
            <select {...login.register("mode")}>
              <option value="login_id">{t("loginId")}</option>
              <option value="email">{t("email")}</option>
            </select>
          </label>
          <label>
            {t(login.watch("mode") === "login_id" ? "loginId" : "email")}
            <input
              {...login.register("identity")}
              type={login.watch("mode") === "email" ? "email" : "text"}
              autoComplete="off"
            />
            <span className="field-error">
              {login.formState.errors.identity && t("invalidIdentity")}
            </span>
          </label>
          {login.watch("mode") === "email" && (
            <label>
              {t("delivery")}
              <select {...login.register("delivery")}>
                <option value="temporary">{t("temporary")}</option>
                <option value="email">{t("emailLink")}</option>
              </select>
            </label>
          )}
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          <button className="primary" disabled={login.formState.isSubmitting}>
            {t("createStudentLogin")}
          </button>
        </form>
      </Sheet>
      <Sheet
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title={t("deletePermanently")}
        description={t("hardDeleteHelp")}
      >
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void archive(true);
          }}
        >
          <label>
            {t("confirmAdmission")}
            <input
              value={confirmation}
              onChange={(e) => setConfirmation(e.target.value)}
              autoComplete="off"
            />
          </label>
          <button
            className="danger"
            disabled={busy || confirmation !== data.admission_number}
          >
            {t("deletePermanently")}
          </button>
        </form>
      </Sheet>
      <Sheet
        open={interestsOpen}
        onOpenChange={setInterestsOpen}
        title={t("editInterests")}
        description={t("interestHelp")}
      >
        <EntityForm
          initial={{ tags: (data.interest_tags || []).join(", ") }}
          fields={[{ name: "tags", label: t("interestTags") }]}
          onSubmit={async (values) => {
            try {
              await api(`/students/${studentId}/`, {
                method: "PATCH",
                body: {
                  interest_tags: String(values.tags)
                    .split(",")
                    .map((x) => x.trim())
                    .filter(Boolean),
                },
              });
              setInterestsOpen(false);
              await refresh();
            } catch (e) {
              setError(String(e));
            }
          }}
        />
      </Sheet>
      <Credentials values={credentials} onClose={() => setCredentials([])} />
    </>
  );
}
