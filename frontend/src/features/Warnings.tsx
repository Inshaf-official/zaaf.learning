import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import { useSession } from "../store";
import { Loading, ErrorState } from "../App";
interface Alert {
  student: number;
  name: string;
  percentage?: number;
  previous?: number;
  current?: number;
}
export default function Warnings() {
  const { t } = useTranslation();
  const member = useSession((s) => s.membership);
  const query = useQuery({
    queryKey: ["warnings", member?.id],
    queryFn: () => api<{ attendance: Alert[]; marks: Alert[] }>("/warnings/"),
  });
  return (
    <>
      <h1>{t("earlyWarning")}</h1>
      {query.isPending ? (
        <Loading />
      ) : query.error ? (
        <ErrorState error={query.error} retry={() => void query.refetch()} />
      ) : (
        ["attendance", "marks"].map((kind) => (
          <section className="panel" key={kind}>
            <h2>
              {t(kind === "attendance" ? "lowAttendance" : "fallingMarks")}
            </h2>
            <ul className="people">
              {query.data[kind as "attendance" | "marks"].map((alert) => (
                <li key={alert.student}>
                  <Link to={`/students/${alert.student}`}>{alert.name}</Link>
                  <span>
                    {alert.percentage !== undefined
                      ? `${alert.percentage}%`
                      : `${alert.previous}% → ${alert.current}%`}
                  </span>
                </li>
              ))}
            </ul>
            {!query.data[kind as "attendance" | "marks"].length && (
              <p>{t("noAlerts")}</p>
            )}
          </section>
        ))
      )}
    </>
  );
}
