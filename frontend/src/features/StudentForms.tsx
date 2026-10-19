import type { UseFormRegister, FieldErrors } from "react-hook-form";
import { useTranslation } from "react-i18next";
import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import type { ReactNode } from "react";
import { labelKey } from "../i18n";
import { useConfig } from "../App";
import type { Credential } from "../types";
import type {
  ClassGroup,
  Division,
  StudentFields,
  GuardianFields,
} from "../lib/student-forms";
export function Sheet({
  open,
  onOpenChange,
  title,
  description,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  children: ReactNode;
}) {
  const { t } = useTranslation();
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="sheet-overlay" />
        <Dialog.Content className="sheet">
          <Dialog.Title>{title}</Dialog.Title>
          <Dialog.Description>{description}</Dialog.Description>
          <Dialog.Close className="sheet-close" aria-label={t("close")}>
            <X />
          </Dialog.Close>
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
export function Credentials({
  values,
  onClose,
}: {
  values: Credential[];
  onClose: () => void;
}) {
  const { t } = useTranslation();
  return (
    <Sheet
      open={values.length > 0}
      onOpenChange={(value) => {
        if (!value) onClose();
      }}
      title={t("accessDetails")}
      description={t("temporaryHelp")}
    >
      {values.map((value) => (
        <div key={value.identity} className="credential">
          <strong>{value.identity}</strong>
          {value.temporary_password ? (
            <output className="secret">{value.temporary_password}</output>
          ) : (
            <p>{t("emailInvitationSent")}</p>
          )}
        </div>
      ))}
      <button className="primary" onClick={onClose}>
        {t("dismiss")}
      </button>
    </Sheet>
  );
}
export function StudentInputs({
  register,
  errors,
  groups,
  divisions,
  selectedGroup,
}: {
  register: UseFormRegister<StudentFields>;
  errors: FieldErrors<StudentFields>;
  groups: ClassGroup[];
  divisions: Division[];
  selectedGroup: string;
}) {
  const { t } = useTranslation();
  const config = useConfig();
  return (
    <>
      <label>
        {t("name")}
        <input {...register("name")} autoComplete="name" />
        <span className="field-error">{errors.name && t("required")}</span>
      </label>
      <label>
        {t("admissionNumber")}
        <input
          {...register("admission_number")}
          autoComplete="off"
          autoCapitalize="none"
        />
        <span className="field-error">
          {errors.admission_number && t("required")}
        </span>
      </label>
      <label>
        {t(labelKey(config.data?.groups.primary || "Class"))}
        <select {...register("class_group")}>
          <option value="">{t("choose")}</option>
          {groups.map((group) => (
            <option key={group.id} value={group.id}>
              {group.name} · {group.academic_year_name}
            </option>
          ))}
        </select>
        <span className="field-error">
          {errors.class_group && t("required")}
        </span>
      </label>
      {config.data?.type !== "TUITION" && (
        <label>
          {t(labelKey(config.data?.groups.secondary || "Division"))}
          <select {...register("division")}>
            <option value="">{t("notAssigned")}</option>
            {divisions
              .filter((d) => String(d.class_group) === selectedGroup)
              .map((division) => (
                <option key={division.id} value={division.id}>
                  {division.name}
                </option>
              ))}
          </select>
        </label>
      )}
      <label>
        {t("dateOfBirth")}
        <input type="date" {...register("date_of_birth")} />
      </label>
      <label>
        {t("joinedOn")}
        <input type="date" {...register("joined_on")} />
        <span className="field-error">{errors.joined_on && t("required")}</span>
      </label>
    </>
  );
}
export function GuardianInputs({
  register,
  errors,
}: {
  register: UseFormRegister<GuardianFields>;
  errors: FieldErrors<GuardianFields>;
}) {
  const { t } = useTranslation();
  return (
    <>
      <label>
        {t("guardianName")}
        <input {...register("name")} autoComplete="name" />
        <span className="field-error">{errors.name && t("required")}</span>
      </label>
      <label>
        {t("email")}
        <input
          type="email"
          inputMode="email"
          {...register("email")}
          autoComplete="email"
        />
        <span className="field-error">{errors.email && t("invalidEmail")}</span>
      </label>
      <label>
        {t("phone")}
        <input
          type="tel"
          inputMode="tel"
          {...register("phone")}
          autoComplete="tel"
        />
        <span className="field-error">{errors.phone && t("invalidPhone")}</span>
      </label>
      <label>
        {t("relationship")}
        <input {...register("relationship")} />
        <span className="field-error">
          {errors.relationship && t("required")}
        </span>
      </label>
      <label>
        {t("delivery")}
        <select {...register("delivery")}>
          <option value="temporary">{t("temporary")}</option>
          <option value="email">{t("emailLink")}</option>
        </select>
      </label>
    </>
  );
}
