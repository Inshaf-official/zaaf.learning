import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import { useSession } from "../store";
import { Loading, ErrorState } from "../App";
interface Row {
  student: number;
  name: string;
  percentage: number;
  total: number;
  alert: boolean;
}
interface Dashboard {
  student_count: number;
  present_today: number;
  absent_today: number;
  alerts: Row[];
  children: Row[];
  can_mark: boolean;
}
export default function DashboardSummary() {
  const { t } = useTranslation();
  const member = useSession((s) => s.membership);
  const query = useQuery({
    queryKey: ["dashboard", member?.id],
    queryFn: () => api<Dashboard>("/dashboard/"),
  });
  if (query.isPending) return <Loading />;
  if (query.error)
    return (
      <ErrorState error={query.error} retry={() => void query.refetch()} />
    );
  const data = query.data;
  return (
    <>
      <section className="stats">
        <article>
          <span>{t("students")}</span>
          <strong>{data.student_count}</strong>
        </article>
        <article>
          <span>{t("presentToday")}</span>
          <strong>{data.present_today}</strong>
          <small>
            {t("absent")}: {data.absent_today}
          </small>
        </article>
      </section>
      {data.can_mark && (
        <Link className="action-card" to="/attendance">
          {t("saveAttendance")}
        </Link>
      )}
      {["ADMIN", "TEACHER"].includes(member?.role || "") && (
        <Link className="action-card" to="/warnings">
          {t("earlyWarning")}
        </Link>
      )}
      <section className="panel">
        <h2>
          {t(
            member?.role === "PARENT" || member?.role === "STUDENT"
              ? "childSummary"
              : "lowAttendance",
          )}
        </h2>
        <ul className="people">
          {(member?.role === "PARENT" || member?.role === "STUDENT"
            ? data.children
            : data.alerts
          ).map((row) => (
            <li key={row.student}>
              <Link to={`/students/${row.student}`}>{row.name}</Link>
              <span>
                {row.total ? `${row.percentage}%` : t("noAttendance")}
              </span>
            </li>
          ))}
        </ul>
        {!data.alerts.length && member?.role !== "PARENT" && (
          <p>{t("noAlerts")}</p>
        )}
      </section>
    </>
  );
}
