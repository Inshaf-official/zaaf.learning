import { hydrateUser } from "../lib/query";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { useSession } from "../store";
import type { Session } from "../types";
export default function Register() {
  const { t } = useTranslation();
  const schema = z.object({
    institution_name: z.string().trim().min(1, t("required")).max(200),
    institution_type: z.enum(["SCHOOL", "TUITION", "MADRASA"]),
    name: z.string().trim().min(1, t("required")).max(150),
    email: z.string().email(t("invalidEmail")),
    password: z.string().min(12, t("shortPassword")).max(128),
  });
  type Fields = z.infer<typeof schema>;
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<Fields>({
    resolver: zodResolver(schema),
    defaultValues: { institution_type: "SCHOOL" },
  });
  const selectedType = watch("institution_type");
  useEffect(() => {
    document.documentElement.dataset.theme = selectedType.toLowerCase();
  }, [selectedType]);
  const [error, setError] = useState("");
  const navigate = useNavigate();
  const client = useQueryClient();
  async function submit(fields: Fields) {
    setError("");
    try {
      const data = await api<Session>("/auth/register/", {
        method: "POST",
        body: fields,
        anonymous: true,
      });
      client.clear();
      if (data.user) hydrateUser(client, data.user);
      useSession.getState().setAccess(data.access);
      navigate("/");
    } catch (e) {
      setError(e instanceof Error ? e.message : t("retry"));
    }
  }
  return (
    <section className="auth-card">
      <h1>{t("register")}</h1>
      <form onSubmit={handleSubmit(submit)} noValidate>
        <label>
          {t("institutionType")}
          <select {...register("institution_type")}>
            <option value="SCHOOL">{t("school")}</option>
            <option value="TUITION">{t("tuition")}</option>
            <option value="MADRASA">{t("madrasa")}</option>
          </select>
        </label>
        <label>
          {t("institutionName")}
          <input
            {...register("institution_name")}
            autoComplete="organization"
          />
          <span className="field-error">
            {errors.institution_name?.message}
          </span>
        </label>
        <label>
          {t("name")}
          <input {...register("name")} autoComplete="name" />
          <span className="field-error">{errors.name?.message}</span>
        </label>
        <label>
          {t("email")}
          <input
            type="email"
            inputMode="email"
            {...register("email")}
            autoComplete="email"
          />
          <span className="field-error">{errors.email?.message}</span>
        </label>
        <label>
          {t("password")}
          <input
            type="password"
            {...register("password")}
            autoComplete="new-password"
          />
          <span className="field-error">{errors.password?.message}</span>
          <small>{t("passwordHelp")}</small>
        </label>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <button className="primary" disabled={isSubmitting}>
          {t("registerAction")}
        </button>
      </form>
      <Link to="/login">{t("back")}</Link>
    </section>
  );
}
