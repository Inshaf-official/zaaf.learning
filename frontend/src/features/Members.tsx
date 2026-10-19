import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Plus, X } from "lucide-react";
import { api } from "../api";
import { useConfig, Loading, ErrorState } from "../App";
import { labelKey } from "../i18n";
import { useSession } from "../store";
import type { InviteResult, Member, Page, Role } from "../types";
export default function Members() {
  const { t } = useTranslation();
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState(false);
  const [secret, setSecret] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loginId, setLoginId] = useState(false);
  const membership = useSession((s) => s.membership);
  const config = useConfig();
  const client = useQueryClient();
  const me = client.getQueryData<{ id: number }>(["me"]);
  const list = useQuery({
    queryKey: ["members", membership?.id, page],
    queryFn: () => api<Page<Member>>(`/members/?page=${page}`),
  });
  const schema = z.object({
    name: z.string().trim().min(1, t("required")).max(150),
    identity: loginId
      ? z.string().regex(/^[a-zA-Z0-9_-]{3,100}$/, t("required"))
      : z.string().email(t("invalidEmail")),
    role: z.enum(["ADMIN", "TEACHER", "PARENT", "STUDENT"]),
    delivery: z.enum(["email", "temporary"]),
  });
  type Fields = z.infer<typeof schema>;
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<Fields>({
    resolver: zodResolver(schema),
    defaultValues: { role: "TEACHER", delivery: "email" },
  });
  async function submit(fields: Fields) {
    setError("");
    try {
      const data = await api<InviteResult>("/members/", {
        method: "POST",
        body: {
          name: fields.name,
          role: loginId ? "STUDENT" : fields.role,
          delivery: loginId ? "temporary" : fields.delivery,
          ...(loginId
            ? { login_id: fields.identity }
            : { email: fields.identity }),
        },
      });
      setSecret(data.temporary_password || "");
      setOpen(false);
      reset();
      setLoginId(false);
      await client.invalidateQueries({ queryKey: ["members"] });
    } catch (e) {
      setError(e instanceof Error ? e.message : t("retry"));
    }
  }
  async function action(member: Member, kind: "activation" | "reset-password") {
    if (
      (kind === "reset-password" || member.is_active) &&
      !window.confirm(
        t(kind === "reset-password" ? "confirmReset" : "confirmDeactivate"),
      )
    )
      return;
    setBusy(true);
    setError("");
    try {
      const data = await api<{ temporary_password?: string }>(
        `/members/${member.id}/${kind}/`,
        {
          method: "POST",
          body: kind === "activation" ? { is_active: !member.is_active } : {},
        },
      );
      if (data.temporary_password) setSecret(data.temporary_password);
      await client.invalidateQueries({ queryKey: ["members"] });
    } catch (e) {
      setError(e instanceof Error ? e.message : t("retry"));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="page-heading">
        <h1>{t("members")}</h1>
        <p className="muted">{t("peopleHelp")}</p>
        <button
          className="primary"
          onClick={() => {
            setError("");
            setOpen(true);
          }}
        >
          <Plus size={20} />
          {t("invite")}
        </button>
      </div>
      {error && !open && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {list.isPending ? (
        <Loading />
      ) : list.error ? (
        <ErrorState error={list.error} retry={() => void list.refetch()} />
      ) : (
        <section className="panel">
          <p className="muted">{t("records", { count: list.data.count })}</p>
          <ul className="people">
            {list.data.results.map((member) => (
              <li key={member.id}>
                <div>
                  <strong>{member.name}</strong>
                  <span>{member.email || member.login_id}</span>
                  <small>
                    {t(
                      labelKey(config.data?.roles[member.role] || member.role),
                    )}{" "}
                    · {t(member.is_active ? "active" : "inactive")}
                  </small>
                </div>
                {member.user_id !== me?.id && (
                  <div className="row-actions">
                    <button
                      disabled={busy}
                      onClick={() => void action(member, "activation")}
                    >
                      {t(member.is_active ? "deactivate" : "reactivate")}
                    </button>
                    <button
                      disabled={busy || !member.is_active}
                      onClick={() => void action(member, "reset-password")}
                    >
                      {t("reset")}
                    </button>
                  </div>
                )}
              </li>
            ))}
          </ul>
          {!list.data.results.length && <p>{t("noPeople")}</p>}
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
      <Dialog.Root open={open} onOpenChange={setOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="sheet-overlay" />
          <Dialog.Content className="sheet">
            <Dialog.Title>{t("invite")}</Dialog.Title>
            <Dialog.Description>{t("peopleHelp")}</Dialog.Description>
            <Dialog.Close className="sheet-close" aria-label={t("dismiss")}>
              <X />
            </Dialog.Close>
            <form onSubmit={handleSubmit(submit)} noValidate>
              <label>
                {t("name")}
                <input {...register("name")} autoComplete="name" />
                <span className="field-error">{errors.name?.message}</span>
              </label>
              {config.data?.type === "SCHOOL" && (
                <label className="check">
                  <input
                    type="checkbox"
                    checked={loginId}
                    onChange={(e) => {
                      setLoginId(e.target.checked);
                      if (e.target.checked) {
                        setValue("role", "STUDENT");
                        setValue("delivery", "temporary");
                      }
                    }}
                  />
                  {t("useLoginId")}
                </label>
              )}
              <label>
                {t(loginId ? "loginId" : "email")}
                <input
                  type={loginId ? "text" : "email"}
                  inputMode={loginId ? "text" : "email"}
                  autoComplete="off"
                  {...register("identity")}
                />
                <span className="field-error">{errors.identity?.message}</span>
              </label>
              {!loginId && (
                <>
                  <label>
                    {t("role")}
                    <select {...register("role")}>
                      {Object.entries(config.data?.roles || {}).map(
                        ([role, label]) => (
                          <option key={role} value={role as Role}>
                            {t(labelKey(label))}
                          </option>
                        ),
                      )}
                    </select>
                  </label>
                  <label>
                    {t("delivery")}
                    <select {...register("delivery")}>
                      <option value="email">{t("emailLink")}</option>
                      <option value="temporary">{t("temporary")}</option>
                    </select>
                  </label>
                </>
              )}
              {error && (
                <p role="alert" className="error">
                  {error}
                </p>
              )}
              <button className="primary" disabled={isSubmitting}>
                {t("inviteAction")}
              </button>
            </form>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
      <Dialog.Root
        open={Boolean(secret)}
        onOpenChange={(value) => {
          if (!value) setSecret("");
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="sheet-overlay" />
          <Dialog.Content className="sheet">
            <Dialog.Title>{t("temporary")}</Dialog.Title>
            <Dialog.Description>{t("temporaryHelp")}</Dialog.Description>
            <output className="secret">{secret}</output>
            <p>
              <a
                target="_blank"
                rel="noopener noreferrer"
                href={`https://wa.me/?text=${encodeURIComponent(t("invitationMessage", { institution: config.data?.name, url: window.location.origin + "/login" }))}`}
              >
                {t("shareInvitation")}
              </a>
            </p>
            <Dialog.Close className="primary">{t("dismiss")}</Dialog.Close>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </>
  );
}
