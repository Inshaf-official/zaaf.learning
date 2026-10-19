import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm, useFieldArray } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useTranslation } from "react-i18next";
import { api, download } from "../api";
import { useSession } from "../store";
import { Loading, ErrorState } from "../App";
import { Sheet } from "./StudentForms";
interface SettingsData {
  name: string;
  address: string;
  language: string;
  attendance_rules: {
    low_threshold: number;
    marks_drop_threshold: number;
    late_edit_policy: string;
    sessions: string[];
  };
  grading_scale: { min: number; grade: string }[];
  has_logo: boolean;
}
const schema = z.object({
  name: z.string().trim().min(1).max(200),
  address: z.string().max(500),
  language: z.enum(["en", "ml"]),
  low_threshold: z.number().min(0).max(100),
  marks_drop_threshold: z.number().min(0).max(100),
  late_edit_policy: z.enum(["ADMIN_ONLY", "BLOCK"]),
  sessions: z.string().min(1),
  grades: z
    .array(
      z.object({
        min: z.number().min(0).max(100),
        grade: z.string().min(1).max(10),
      }),
    )
    .min(1)
    .max(20),
});
type Fields = z.infer<typeof schema>;
function SettingsForm({ data }: { data: SettingsData }) {
  const { t, i18n } = useTranslation();
  const client = useQueryClient();
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [confirm, setConfirm] = useState("");
  const {
    register,
    control,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<Fields>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: data.name,
      address: data.address,
      language: data.language as "en" | "ml",
      ...data.attendance_rules,
      sessions: data.attendance_rules.sessions.join(", "),
      late_edit_policy: data.attendance_rules.late_edit_policy as
        "ADMIN_ONLY" | "BLOCK",
      grades: data.grading_scale,
    },
  });
  const grades = useFieldArray({ control, name: "grades" });
  async function save(fields: Fields) {
    setError("");
    try {
      await api("/institution/settings/", {
        method: "PATCH",
        body: {
          name: fields.name,
          address: fields.address,
          language: fields.language,
          attendance_rules: {
            low_threshold: fields.low_threshold,
            marks_drop_threshold: fields.marks_drop_threshold,
            late_edit_policy: fields.late_edit_policy,
            sessions: fields.sessions
              .split(",")
              .map((x) => x.trim().toUpperCase())
              .filter(Boolean),
          },
          grading_scale: fields.grades,
        },
      });
      void i18n.changeLanguage(fields.language);
      await client.invalidateQueries();
      setMessage(t("saved"));
    } catch (e) {
      setError(String(e));
    }
  }
  return (
    <>
      <section className="panel">
        <form onSubmit={handleSubmit(save)} noValidate>
          <label>
            {t("institutionName")}
            <input {...register("name")} />
          </label>
          <label>
            {t("address")}
            <textarea {...register("address")} />
          </label>
          <label>
            {t("language")}
            <select {...register("language")}>
              <option value="en">English</option>
              <option value="ml">മലയാളം</option>
            </select>
          </label>
          <label>
            {t("lowThreshold")}
            <input
              type="number"
              inputMode="numeric"
              min={0}
              max={100}
              {...register("low_threshold", { valueAsNumber: true })}
            />
          </label>
          <label>
            {t("marksDropThreshold")}
            <input
              type="number"
              inputMode="numeric"
              min={0}
              max={100}
              {...register("marks_drop_threshold", { valueAsNumber: true })}
            />
          </label>
          <label>
            {t("lateEditPolicy")}
            <select {...register("late_edit_policy")}>
              <option value="ADMIN_ONLY">{t("adminApproval")}</option>
              <option value="BLOCK">{t("locked")}</option>
            </select>
          </label>
          <label>
            {t("attendanceSessions")}
            <input {...register("sessions")} />
          </label>
          <h2>{t("gradingScale")}</h2>
          {grades.fields.map((field, index) => (
            <fieldset key={field.id}>
              <legend>
                {t("grade")} {index + 1}
              </legend>
              <label>
                {t("minimumPercent")}
                <input
                  type="number"
                  inputMode="numeric"
                  min={0}
                  max={100}
                  {...register(`grades.${index}.min`, { valueAsNumber: true })}
                />
              </label>
              <label>
                {t("grade")}
                <input {...register(`grades.${index}.grade`)} />
              </label>
              <button
                type="button"
                disabled={grades.fields.length <= 1}
                onClick={() => grades.remove(index)}
              >
                {t("remove")}
              </button>
            </fieldset>
          ))}
          <button
            type="button"
            disabled={grades.fields.length >= 20}
            onClick={() => grades.append({ min: 0, grade: "" })}
          >
            {t("addGrade")}
          </button>
          {Object.keys(errors).length > 0 && (
            <p className="error" role="alert">
              {t("checkSettings")}
            </p>
          )}
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          {message && <p role="status">{message}</p>}
          <button className="primary" disabled={isSubmitting}>
            {t("save")}
          </button>
        </form>
      </section>
      <section className="panel">
        <h2>{t("institutionLogo")}</h2>
        <label>
          {t("uploadLogo")}
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (!file) return;
              const body = new FormData();
              body.set("logo", file);
              void api("/institution/logo/", { method: "POST", body })
                .then(() => setMessage(t("saved")))
                .catch((error) => setError(String(error)));
            }}
          />
        </label>
        <small>{t("logoHelp")}</small>
      </section>
      <section className="panel">
        <h2>{t("privacyControls")}</h2>
        <button
          onClick={() =>
            void download(
              "/institution/export/",
              "institution-export.zip",
            ).catch((error) => setError(String(error)))
          }
        >
          {t("exportInstitution")}
        </button>
        <button className="danger-outline" onClick={() => setDeleting(true)}>
          {t("deleteInstitution")}
        </button>
      </section>
      <Sheet
        open={deleting}
        onOpenChange={setDeleting}
        title={t("deleteInstitution")}
        description={t("deleteInstitutionHelp")}
      >
        <form
          onSubmit={async (event) => {
            event.preventDefault();
            try {
              await api("/institution/delete/", {
                method: "POST",
                body: { confirmation: confirm },
              });
              useSession.getState().clear();
              client.clear();
              window.location.assign("/login");
            } catch (e) {
              setError(String(e));
            }
          }}
        >
          <label>
            {t("typeToConfirm")} DELETE {data.name}
            <input
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              autoComplete="off"
            />
          </label>
          <button
            className="danger"
            disabled={confirm !== `DELETE ${data.name}`}
          >
            {t("deleteInstitution")}
          </button>
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
        </form>
      </Sheet>
    </>
  );
}
export default function Settings() {
  const { t } = useTranslation();
  const member = useSession((s) => s.membership);
  const query = useQuery({
    queryKey: ["settings", member?.id],
    queryFn: () => api<SettingsData>("/institution/settings/"),
  });
  return (
    <>
      <h1>{t("settings")}</h1>
      {query.isPending ? (
        <Loading />
      ) : query.error ? (
        <ErrorState error={query.error} retry={() => void query.refetch()} />
      ) : (
        <SettingsForm data={query.data} />
      )}
    </>
  );
}
