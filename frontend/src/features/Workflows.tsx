import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useConfig, Loading, ErrorState } from "../App";
import { useSession } from "../store";
export default function Workflows() {
  const { t } = useTranslation();
  const config = useConfig();
  const member = useSession((s) => s.membership);
  if (config.isPending) return <Loading />;
  if (config.error)
    return (
      <ErrorState error={config.error} retry={() => void config.refetch()} />
    );
  const links = [
    { to: "/students", key: "feeNotes", module: "fee_notes" },
    { to: "/madrasa", key: "madrasaLearning", module: "hifz" },
    { to: "/tuition", key: "tuitionManagement", module: "fees" },
    { to: "/events", key: "events", module: "events" },
    { to: "/notices", key: "notices", module: "notices" },
    ...(["ADMIN", "TEACHER"].includes(member?.role || "")
      ? [{ to: "/warnings", key: "earlyWarning", module: "" }]
      : []),
    { to: "/attendance", key: "attendance", module: "attendance" },
    {
      to: "/exams",
      key: "exams",
      module: config.data.type === "TUITION" ? "tests" : "exams",
    },
    ...(member?.role === "ADMIN"
      ? [
          { to: "/settings", key: "settings", module: "" },
          { to: "/people", key: "members", module: "" },
          { to: "/setup", key: "academicSetup", module: "" },
        ]
      : []),
  ];
  return (
    <>
      <h1>{t("work")}</h1>
      <div className="workflow-grid">
        {links
          .filter(
            (link) => !link.module || config.data.modules.includes(link.module),
          )
          .map((link) => (
            <Link key={link.to} className="action-card" to={link.to}>
              <h2>{t(link.key)}</h2>
            </Link>
          ))}
      </div>
    </>
  );
}
