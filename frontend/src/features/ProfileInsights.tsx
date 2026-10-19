import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import { useSession } from "../store";
import { Loading, ErrorState } from "../App";
interface Insights {
  attendance: {
    total: number;
    attended: number;
    percentage: number | null;
    streak: number;
  };
  trend: { exam: string; percentage: number }[];
  events: { id: number; name: string; date: string; status: string }[];
}
export default function ProfileInsights({ studentId }: { studentId: number }) {
  const { t } = useTranslation();
  const member = useSession((s) => s.membership);
  const query = useQuery({
    queryKey: ["insights", member?.id, studentId],
    queryFn: () => api<Insights>(`/students/${studentId}/insights/`),
  });
  if (query.isPending) return <Loading />;
  if (query.error)
    return (
      <ErrorState error={query.error} retry={() => void query.refetch()} />
    );
  const data = query.data;
  const points = data.trend
    .map(
      (point, i) =>
        `${20 + i * (280 / Math.max(1, data.trend.length - 1))},${120 - point.percentage}`,
    )
    .join(" ");
  return (
    <>
      <section className="stats">
        <article>
          <span>{t("attendance")}</span>
          <strong>
            {data.attendance.percentage === null
              ? t("noAttendance")
              : data.attendance.percentage + "%"}
          </strong>
          <small>
            {data.attendance.attended}/{data.attendance.total}
          </small>
        </article>
        <article>
          <span>{t("attendanceStreak")}</span>
          <strong>{data.attendance.streak}</strong>
        </article>
      </section>
      <section className="panel">
        <h2>{t("marksTrend")}</h2>
        {data.trend.length ? (
          <>
            <svg
              role="img"
              aria-label={t("marksTrend")}
              viewBox="0 0 320 140"
              width="320"
              height="140"
              style={{ maxWidth: "100%", height: "auto" }}
            >
              <line x1="20" y1="120" x2="300" y2="120" stroke="var(--line)" />
              <polyline
                points={points}
                stroke="var(--primary)"
                strokeWidth="3"
                fill="none"
              />
              {data.trend.map((point, i) => (
                <circle
                  key={i}
                  cx={20 + (i * 280) / Math.max(1, data.trend.length - 1)}
                  cy={120 - point.percentage}
                  r="4"
                  fill="var(--accent)"
                />
              ))}
            </svg>
            <ul className="people">
              {data.trend.map((point, i) => (
                <li key={i}>
                  <span>{point.exam}</span>
                  <strong>{point.percentage}%</strong>
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p>{t("noPublishedMarks")}</p>
        )}
      </section>
      <section className="panel">
        <h2>{t("events")}</h2>
        <ul className="people">
          {data.events.map((event) => (
            <li key={event.id}>
              <strong>{event.name}</strong>
              <span>{t(event.status.toLowerCase())}</span>
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
