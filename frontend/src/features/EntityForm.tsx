import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useTranslation } from "react-i18next";
export interface FormField {
  name: string;
  label: string;
  type?:
    "text" | "date" | "number" | "textarea" | "checkbox" | "select" | "time";
  options?: { value: string; label: string }[];
  required?: boolean;
  min?: number;
  max?: number;
  step?: string;
}
export type FormValues = Record<string, string | boolean>;
export default function EntityForm({
  fields,
  initial = {},
  onSubmit,
  submitLabel,
}: {
  fields: FormField[];
  initial?: FormValues;
  onSubmit: (data: FormValues) => Promise<void>;
  submitLabel?: string;
}) {
  const { t } = useTranslation();
  const schema = z
    .record(z.union([z.string(), z.boolean()]))
    .superRefine((data, ctx) => {
      for (const field of fields) {
        if (field.required && !String(data[field.name] ?? "").trim())
          ctx.addIssue({
            code: "custom",
            path: [field.name],
            message: t("required"),
          });
        if (
          field.type === "number" &&
          data[field.name] !== "" &&
          data[field.name] !== undefined
        ) {
          const number = Number(data[field.name]);
          if (
            !Number.isFinite(number) ||
            (field.min !== undefined && number < field.min) ||
            (field.max !== undefined && number > field.max)
          )
            ctx.addIssue({
              code: "custom",
              path: [field.name],
              message: t("invalidNumber"),
            });
        }
      }
    });
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: Object.fromEntries(
      fields.map((field) => [
        field.name,
        initial[field.name] ?? (field.type === "checkbox" ? false : ""),
      ]),
    ),
  });
  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate>
      {fields.map((field) => (
        <label
          key={field.name}
          className={field.type === "checkbox" ? "check" : ""}
        >
          {field.type !== "checkbox" && field.label}
          {field.type === "select" ? (
            <select {...register(field.name)}>
              <option value="">{t("choose")}</option>
              {field.options?.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          ) : field.type === "textarea" ? (
            <textarea rows={4} {...register(field.name)} maxLength={4000} />
          ) : (
            <input
              type={field.type || "text"}
              inputMode={field.type === "number" ? "decimal" : undefined}
              min={field.min}
              max={field.max}
              step={field.step || "any"}
              {...register(field.name)}
            />
          )}{" "}
          {field.type === "checkbox" && field.label}
          <span className="field-error">{errors[field.name]?.message}</span>
        </label>
      ))}
      <button className="primary" disabled={isSubmitting}>
        {submitLabel || t("save")}
      </button>
    </form>
  );
}
