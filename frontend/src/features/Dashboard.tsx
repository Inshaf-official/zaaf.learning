import { lazy, Suspense } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ShieldCheck, Users, BookOpen } from "lucide-react";
import { useConfig, Loading, ErrorState } from "../App";
import { useCan } from "../store";
import { labelKey } from "../i18n";
import type { User } from "../types";
const DashboardSummary = lazy(() => import("./DashboardSummary"));
const MedicalAlerts = lazy(() => import("./MedicalAlerts"));
export default function Dashboard({ user }: { user: User }) {
  const { t } = useTranslation();
  const config = useConfig();
  const canManage = useCan("members.manage");
  if (config.isPending) return <Loading />;
  if (config.error)
    return (
      <ErrorState error={config.error} retry={() => void config.refetch()} />
    );
  const data = config.data;
  return (
    <>
      <div className="page-heading">
        <p className="eyebrow">{data.name}</p>
        <h1>
          {t("welcome")}, {user.name}
        </h1>
        <p className="muted">{t("workspaceHelp")}</p>
      </div>
      <Suspense fallback={<Loading />}>
        <DashboardSummary />
      </Suspense>
      <section className="context-banner">
        <ShieldCheck size={28} />
        <div>
          <span>{t("activeRole")}</span>
          <h2>{t(labelKey(data.roles[data.role] || data.role))}</h2>
        </div>
      </section>
      <div className="stats">
        <article>
          <BookOpen />
          <span>{t("grouping")}</span>
          <strong>
            {t(labelKey(data.groups.primary))} /{" "}
            {t(labelKey(data.groups.secondary))}
          </strong>
        </article>
        <article>
          <span>{t("attendanceMode")}</span>
          <strong>{t(labelKey(data.attendance_mode))}</strong>
        </article>
      </div>
      {canManage && (
        <Link className="action-card" to="/people">
          <Users />
          <div>
            <h2>{t("invite")}</h2>
            <p>{t("peopleHelp")}</p>
          </div>
        </Link>
      )}
      <Link className="action-card" to="/students">
        <BookOpen />
        <div>
          <h2>{t("students")}</h2>
          <p>{t("studentsHelp")}</p>
        </div>
      </Link>
      {canManage && (
        <Suspense fallback={<Loading />}>
          <MedicalAlerts />
        </Suspense>
      )}
      <p className="notice">{t("phaseNotice")}</p>
    </>
  );
}
