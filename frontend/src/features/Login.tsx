import { hydrateUser } from "../lib/query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Link, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import { useSession } from "../store";
import type { Session } from "../types";
export default function Login() {
  const { t } = useTranslation();
  const schema = z.object({
    identifier: z.string().trim().min(1, t("required")),
    password: z.string().min(1, t("required")),
  });
  type Fields = z.infer<typeof schema>;
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<Fields>({ resolver: zodResolver(schema) });
  const [error, setError] = useState("");
  const navigate = useNavigate();
  const client = useQueryClient();
  async function submit(fields: Fields) {
    setError("");
    try {
      const data = await api<Session>("/auth/login/", {
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
      <p className="eyebrow">{t("office")}</p>
      <h1>{t("signIn")}</h1>
      <p className="muted">{t("secure")}</p>
      <form onSubmit={handleSubmit(submit)} noValidate>
        <label>
          {t("emailId")}
          <input
            {...register("identifier")}
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
            aria-invalid={Boolean(errors.identifier)}
          />
          <span className="field-error">{errors.identifier?.message}</span>
        </label>
        <label>
          {t("password")}
          <input
            type="password"
            {...register("password")}
            autoComplete="current-password"
            aria-invalid={Boolean(errors.password)}
          />
          <span className="field-error">{errors.password?.message}</span>
        </label>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        <button className="primary" disabled={isSubmitting}>
          {t("signIn")}
        </button>
      </form>
      <Link to="/forgot-password">{t("forgot")}</Link>
      <div className="divider" />
      <Link to="/register">{t("register")}</Link>
    </section>
  );
}
