import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm, useFieldArray } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useTranslation } from "react-i18next";
import { Phone, ShieldAlert, Plus, Trash2 } from "lucide-react";
import { api, ApiError } from "../api";
import { useSession } from "../store";
import { Loading, ErrorState } from "../App";
import { indianDate } from "../lib/student-forms";
import type { MedicalResponse, Grant } from "../types";
const schema = z.object({
  blood_group: z.string(),
  allergies: z.string().max(4000),
  conditions: z.string().max(4000),
  doctor: z.string().max(250),
  emergency_contacts: z
    .array(
      z.object({
        name: z.string().trim().min(1).max(150),
        relationship: z.string().max(50),
        phone: z.string().regex(/^\+?[0-9 ()-]{6,25}$/),
      }),
    )
    .max(10),
});
type Fields = z.infer<typeof schema>;
export default function MedicalCard({ studentId }: { studentId: number }) {
  const { t } = useTranslation();
  const member = useSession((s) => s.membership);
  const key = ["medical", member?.id, studentId];
  const client = useQueryClient();
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false);
  const [clock, setClock] = useState(Date.now());
  const medical = useQuery({
    queryKey: key,
    queryFn: () => api<MedicalResponse>(`/students/${studentId}/medical/`),
    retry: false,
    staleTime: 0,
    gcTime: 0,
    refetchOnWindowFocus: "always",
  });
  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<Fields>({
    resolver: zodResolver(schema),
    defaultValues: {
      blood_group: "",
      allergies: "",
      conditions: "",
      doctor: "",
      emergency_contacts: [],
    },
  });
  const contacts = useFieldArray({ control, name: "emergency_contacts" });
  const expires = medical.data?.access_expires_at;
  const expired = Boolean(expires && new Date(expires).getTime() <= clock);
  useEffect(() => {
    if (!expires) return;
    const interval = window.setInterval(() => setClock(Date.now()), 1000);
    return () => window.clearInterval(interval);
  }, [expires]);
  useEffect(() => {
    if (expired) {
      client.removeQueries({ queryKey: key });
      void medical.refetch();
    }
  }, [expired]);
  async function unlock() {
    setBusy(true);
    setError("");
    try {
      await api<Grant>(`/students/${studentId}/break-glass/`, {
        method: "POST",
        body: { reason },
      });
      setReason("");
      setClock(Date.now());
      await medical.refetch();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("retry"));
    } finally {
      setBusy(false);
    }
  }
  async function save(fields: Fields) {
    setError("");
    try {
      await api<MedicalResponse>(`/students/${studentId}/medical/`, {
        method: "PUT",
        body: fields,
      });
      setEditing(false);
      await medical.refetch();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("retry"));
    }
  }
  if (medical.isPending) return <Loading />;
  if (medical.error || expired) {
    const forbidden =
      expired ||
      (medical.error instanceof ApiError && medical.error.status === 403);
    if (!forbidden && medical.error)
      return (
        <ErrorState
          error={medical.error}
          retry={() => void medical.refetch()}
        />
      );
    return (
      <section className="panel medical-locked">
        <ShieldAlert />
        <h2>{t("medicalRestricted")}</h2>
        <p>{t("medicalPrivacy")}</p>
        {member?.role === "TEACHER" && (
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void unlock();
            }}
          >
            <label>
              {t("emergencyReason")}
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                minLength={10}
                maxLength={1000}
                required
                rows={4}
              />
            </label>
            <p className="notice">{t("breakGlassHelp")}</p>
            {error && (
              <p role="alert" className="error">
                {error}
              </p>
            )}
            <button
              className="primary"
              disabled={busy || reason.trim().length < 10}
            >
              {t("unlockMedical")}
            </button>
          </form>
        )}
      </section>
    );
  }
  const data = medical.data;
  const card = data.card;
  return (
    <section className="panel medical-card">
      <div className="section-heading">
        <h2>{t("medicalCard")}</h2>
        {data.can_edit && !editing && (
          <button
            onClick={() => {
              reset(
                card
                  ? {
                      ...card,
                      emergency_contacts: card.emergency_contacts.map((c) => ({
                        ...c,
                        relationship: c.relationship || "",
                      })),
                    }
                  : {
                      blood_group: "",
                      allergies: "",
                      conditions: "",
                      doctor: "",
                      emergency_contacts: [],
                    },
              );
              setEditing(true);
            }}
          >
            {t("edit")}
          </button>
        )}
      </div>
      {expires && (
        <p className="notice">
          {t("accessUntil")}{" "}
          {new Intl.DateTimeFormat("en-IN", {
            hour: "2-digit",
            minute: "2-digit",
            timeZone: "Asia/Kolkata",
          }).format(new Date(expires))}
        </p>
      )}
      {editing ? (
        <form onSubmit={handleSubmit(save)} noValidate>
          <label>
            {t("bloodGroup")}
            <select {...register("blood_group")}>
              <option value="">{t("notRecorded")}</option>
              {["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"].map(
                (group) => (
                  <option key={group}>{group}</option>
                ),
              )}
            </select>
          </label>
          <label>
            {t("allergies")}
            <textarea {...register("allergies")} rows={3} maxLength={4000} />
          </label>
          <label>
            {t("conditions")}
            <textarea {...register("conditions")} rows={3} maxLength={4000} />
          </label>
          <label>
            {t("doctor")}
            <input {...register("doctor")} maxLength={250} />
          </label>
          <h3>{t("emergencyContacts")}</h3>
          {contacts.fields.map((field, index) => (
            <fieldset key={field.id}>
              <legend>
                {t("contact")} {index + 1}
              </legend>
              <label>
                {t("name")}
                <input {...register(`emergency_contacts.${index}.name`)} />
              </label>
              <label>
                {t("relationship")}
                <input
                  {...register(`emergency_contacts.${index}.relationship`)}
                />
              </label>
              <label>
                {t("phone")}
                <input
                  type="tel"
                  inputMode="tel"
                  {...register(`emergency_contacts.${index}.phone`)}
                />
              </label>
              <button type="button" onClick={() => contacts.remove(index)}>
                <Trash2 size={18} />
                {t("remove")}
              </button>
            </fieldset>
          ))}
          <button
            type="button"
            disabled={contacts.fields.length >= 10}
            onClick={() =>
              contacts.append({ name: "", phone: "", relationship: "" })
            }
          >
            <Plus size={18} />
            {t("addContact")}
          </button>
          {Object.keys(errors).length > 0 && (
            <p className="error" role="alert">
              {t("checkContacts")}
            </p>
          )}
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          <div className="form-actions">
            <button
              type="button"
              onClick={() => {
                reset();
                setEditing(false);
              }}
            >
              {t("cancel")}
            </button>
            <button className="primary" disabled={isSubmitting}>
              {t("saveMedical")}
            </button>
          </div>
        </form>
      ) : card ? (
        <>
          <div className="blood-group">
            <span>{t("bloodGroup")}</span>
            <strong>{card.blood_group || t("notRecorded")}</strong>
          </div>
          <dl className="details">
            <dt>{t("allergies")}</dt>
            <dd className={card.allergies ? "critical-text" : ""}>
              {card.allergies || t("notRecorded")}
            </dd>
            <dt>{t("conditions")}</dt>
            <dd>{card.conditions || t("notRecorded")}</dd>
            <dt>{t("doctor")}</dt>
            <dd>{card.doctor || t("notRecorded")}</dd>
          </dl>
          <h3>{t("emergencyContacts")}</h3>
          {card.emergency_contacts.length ? (
            card.emergency_contacts.map((contact, index) => (
              <div className="emergency-contact" key={index}>
                <div>
                  <strong>{contact.name}</strong>
                  <span>{contact.relationship}</span>
                </div>
                <a
                  className="call-button"
                  href={`tel:${contact.phone.replace(/[^+0-9]/g, "")}`}
                >
                  <Phone size={18} />
                  {contact.phone}
                </a>
              </div>
            ))
          ) : (
            <p className="muted">{t("noContacts")}</p>
          )}
          <small>
            {t("updated")} {indianDate(card.updated_at)}
          </small>
        </>
      ) : (
        <p className="notice">{t("noMedical")}</p>
      )}
    </section>
  );
}
