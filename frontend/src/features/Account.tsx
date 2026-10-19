import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import { useSession } from "../store";
import type { Session } from "../types";
export default function Account({
  publicFlow,
  forced = false,
}: {
  publicFlow?: "set" | "request";
  forced?: boolean;
}) {
  const { t } = useTranslation();
  const [params] = useSearchParams();
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();
  const client = useQueryClient();
  const schema = z.object({
    email:
      publicFlow === "request"
        ? z.string().email(t("invalidEmail"))
        : z.string().optional(),
    current_password: publicFlow
      ? z.string().optional()
      : z.string().min(1, t("required")),
    password:
      publicFlow === "request"
        ? z.string().optional()
        : z.string().min(12, t("shortPassword")).max(128),
  });
  type Fields = z.infer<typeof schema>;
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<Fields>({ resolver: zodResolver(schema) });
  async function submit(fields: Fields) {
    setError("");
    setMessage("");
    try {
      if (publicFlow === "request") {
        await api("/auth/request-password/", {
          method: "POST",
          body: { email: fields.email },
          anonymous: true,
        });
        setMessage(t("linkSent"));
      } else if (publicFlow === "set") {
        await api("/auth/set-password/", {
          method: "POST",
          body: { token: params.get("token"), password: fields.password },
          anonymous: true,
        });
        setMessage(t("passwordSaved"));
      } else {
        const data = await api<Session>("/auth/change-password/", {
          method: "POST",
          body: {
            current_password: fields.current_password,
            new_password: fields.password,
          },
        });
        useSession.getState().setAccess(data.access);
        await client.invalidateQueries({ queryKey: ["me"] });
        setMessage(t("passwordSaved"));
        if (forced) navigate("/");
      }
      reset();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("retry"));
    }
  }
  return (
    <section className={publicFlow ? "auth-card" : "panel narrow"}>
      <h1>
        {t(
          publicFlow === "request"
            ? "forgot"
            : publicFlow === "set"
              ? "setPassword"
              : "changePassword",
        )}
      </h1>
      {forced && <p className="notice">{t("forcePassword")}</p>}
      <form onSubmit={handleSubmit(submit)} noValidate>
        {publicFlow === "request" ? (
          <label>
            {t("email")}
            <input
              type="email"
              inputMode="email"
              autoComplete="email"
              {...register("email")}
            />
            <span className="field-error">{errors.email?.message}</span>
          </label>
        ) : (
          <>
            {!publicFlow && (
              <label>
                {t("currentPassword")}
                <input
                  type="password"
                  autoComplete="current-password"
                  {...register("current_password")}
                />
                <span className="field-error">
                  {errors.current_password?.message}
                </span>
              </label>
            )}
            <label>
              {t("newPassword")}
              <input
                type="password"
                autoComplete="new-password"
                {...register("password")}
              />
              <span className="field-error">{errors.password?.message}</span>
              <small>{t("passwordHelp")}</small>
            </label>
          </>
        )}
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        {message && (
          <p role="status" className="success">
            {message}
          </p>
        )}
        <button className="primary" disabled={isSubmitting}>
          {t(publicFlow === "request" ? "sendLink" : "savePassword")}
        </button>
      </form>
      {publicFlow && <Link to="/login">{t("back")}</Link>}
    </section>
  );
}
