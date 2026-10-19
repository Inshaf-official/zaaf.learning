import { lazy, Suspense, useEffect, useState } from "react";
import {
  Link,
  NavLink,
  Navigate,
  Route,
  Routes,
  useNavigate,
} from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BookOpen,
  Home,
  UserRound,
  LogOut,
  GraduationCap,
  LayoutGrid,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { api, restore } from "./api";
import { useSession } from "./store";
import { labelKey } from "./i18n";
import type { InstitutionConfig, User } from "./types";
const Login = lazy(() => import("./features/Login"));
const Register = lazy(() => import("./features/Register"));
const Dashboard = lazy(() => import("./features/Dashboard"));
const Account = lazy(() => import("./features/Account"));
const Members = lazy(() => import("./features/Members"));
const Workflows = lazy(() => import("./features/Workflows"));
const PwaUpdate = lazy(() => import("./features/PwaUpdate"));
const InstitutionLogo = lazy(() => import("./features/InstitutionLogo"));
const Settings = lazy(() => import("./features/Settings"));
const Madrasa = lazy(() => import("./features/Madrasa"));
const Tuition = lazy(() => import("./features/Tuition"));
const Events = lazy(() => import("./features/Events"));
const Notices = lazy(() => import("./features/Notices"));
const Warnings = lazy(() => import("./features/Warnings"));
const Exams = lazy(() => import("./features/Exams"));
const Attendance = lazy(() => import("./features/Attendance"));
const Students = lazy(() => import("./features/Students"));
const StudentProfile = lazy(() => import("./features/StudentProfile"));
const AcademicSetup = lazy(() => import("./features/AcademicSetup"));
export function Loading() {
  const { t } = useTranslation();
  return (
    <div className="skeletons" role="status" aria-label={t("loading")}>
      <div />
      <div />
      <div />
    </div>
  );
}
export function ErrorState({
  error,
  retry,
}: {
  error: Error;
  retry: () => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="error" role="alert">
      <p>{error.message}</p>
      <button onClick={retry}>{t("retry")}</button>
    </div>
  );
}
export function Preferences() {
  const { t, i18n } = useTranslation();
  const [dark, setDark] = useState(localStorage.getItem("mode") === "dark");
  useEffect(() => {
    document.documentElement.dataset.mode = dark ? "dark" : "light";
    localStorage.setItem("mode", dark ? "dark" : "light");
  }, [dark]);
  return (
    <div className="preferences">
      <label>
        <span className="sr-only">{t("language")}</span>
        <select
          aria-label={t("language")}
          value={i18n.language}
          onChange={(e) => void i18n.changeLanguage(e.target.value)}
        >
          <option value="en">English</option>
          <option value="ml">മലയാളം</option>
        </select>
      </label>
      <button
        type="button"
        onClick={() => setDark(!dark)}
        aria-label={`${t("appearance")}: ${t(dark ? "light" : "dark")}`}
      >
        {t(dark ? "light" : "dark")}
      </button>
    </div>
  );
}
export function useConfig() {
  const member = useSession((s) => s.membership);
  return useQuery({
    queryKey: ["config", member?.id],
    queryFn: () => api<InstitutionConfig>("/institution/config/"),
    enabled: Boolean(member),
  });
}
export default function App() {
  const { t } = useTranslation();
  const access = useSession((s) => s.access);
  const membership = useSession((s) => s.membership);
  const select = useSession((s) => s.select);
  const [booting, setBooting] = useState(true);
  const [bootError, setBootError] = useState<Error | null>(null);
  const [online, setOnline] = useState(navigator.onLine);
  const client = useQueryClient();
  const navigate = useNavigate();
  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => api<User>("/auth/me/"),
    enabled: Boolean(access),
  });
  const config = useConfig();
  const boot = () => {
    setBooting(true);
    setBootError(null);
    void restore()
      .catch((error: Error) => setBootError(error))
      .finally(() => setBooting(false));
  };
  useEffect(boot, []);
  useEffect(() => {
    const update = () => setOnline(navigator.onLine);
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);
  useEffect(() => {
    if (
      me.data &&
      (!membership || !me.data.memberships.some((m) => m.id === membership.id))
    )
      select(me.data.memberships[0] || null);
  }, [me.data, membership, select]);
  useEffect(() => {
    document.documentElement.dataset.theme =
      membership?.type.toLowerCase() || "school";
    const color =
      membership?.type === "TUITION"
        ? "#0F766E"
        : membership?.type === "MADRASA"
          ? "#14532D"
          : "#1F3A5F";
    document
      .querySelector("meta[name=theme-color]")
      ?.setAttribute("content", color);
  }, [membership]);
  async function signOut() {
    await api<void>("/auth/logout/", { method: "POST", anonymous: true });
    navigator.serviceWorker?.controller?.postMessage({
      type: "CLEAR_PRIVATE_CACHE",
    });
    useSession.getState().clear();
    client.clear();
    navigate("/login");
  }
  if (booting) return <Loading />;
  if (bootError) return <ErrorState error={bootError} retry={boot} />;
  const menu = [
    { path: "/", key: "home", icon: Home },
    { path: "/students", key: "students", icon: GraduationCap },
    { path: "/work", key: "work", icon: LayoutGrid },
    { path: "/account", key: "account", icon: UserRound },
  ];
  return (
    <>
      <Suspense fallback={null}>
        <PwaUpdate />
      </Suspense>
      {!online && (
        <div className="offline" role="status">
          {t("offline")}
        </div>
      )}
      {!access ? (
        <main className="auth">
          <header className="brand">
            <BookOpen aria-hidden="true" />
            <Link to="/login">{t("office")}</Link>
          </header>
          <Preferences />
          <Suspense fallback={<Loading />}>
            <Routes>
              <Route path="/register" element={<Register />} />
              <Route
                path="/set-password"
                element={<Account publicFlow="set" />}
              />
              <Route
                path="/forgot-password"
                element={<Account publicFlow="request" />}
              />
              <Route path="*" element={<Login />} />
            </Routes>
          </Suspense>
        </main>
      ) : me.isPending ? (
        <Loading />
      ) : me.error ? (
        <ErrorState error={me.error} retry={() => void me.refetch()} />
      ) : (
        me.data && (
          <div className="layout">
            <aside className="sidebar">
              <div className="brand">
                <BookOpen aria-hidden="true" />
                <strong>{t("office")}</strong>
              </div>
              <nav aria-label={t("office")}>
                {!me.data.must_change_password &&
                  menu.map((item) => (
                    <NavLink
                      key={item.path}
                      to={item.path}
                      end={item.path === "/"}
                    >
                      <item.icon size={20} />
                      {t(item.key)}
                    </NavLink>
                  ))}
              </nav>
              <button
                onClick={() =>
                  void signOut().catch((error: Error) => setBootError(error))
                }
              >
                <LogOut size={18} />
                {t("signOut")}
              </button>
            </aside>
            <div className="workspace">
              <header className="topbar">
                <div className="identity-context">
                  <Suspense fallback={null}>
                    <InstitutionLogo />
                  </Suspense>
                  <label className="context">
                    <span className="sr-only">{t("selectContext")}</span>
                    <select
                      value={membership?.id || ""}
                      onChange={(e) => {
                        const selected = me.data?.memberships.find(
                          (m) => m.id === Number(e.target.value),
                        );
                        if (selected) {
                          client.removeQueries({
                            predicate: (q) => q.queryKey[0] !== "me",
                          });
                          select(selected);
                          navigate("/");
                        }
                      }}
                    >
                      {me.data.memberships.map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.institution_name} ·{" "}
                          {t(
                            labelKey(
                              m.config?.roles[m.role] ||
                                config.data?.roles[m.role] ||
                                {
                                  ADMIN:
                                    m.type === "SCHOOL"
                                      ? "Principal"
                                      : m.type === "TUITION"
                                        ? "Head"
                                        : "Admin",
                                  TEACHER:
                                    m.type === "MADRASA" ? "Ustad" : "Teacher",
                                  PARENT: "Parent",
                                  STUDENT: "Student",
                                }[m.role],
                            ),
                          )}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <Preferences />
                <button
                  className="mobile-signout"
                  aria-label={t("signOut")}
                  onClick={() =>
                    void signOut().catch((error: Error) => setBootError(error))
                  }
                >
                  <LogOut size={20} />
                </button>
              </header>
              <main id="main">
                <Suspense fallback={<Loading />}>
                  {me.data.must_change_password ? (
                    <Account forced />
                  ) : (
                    <Routes>
                      <Route path="/" element={<Dashboard user={me.data} />} />
                      <Route
                        path="/people"
                        element={
                          membership?.role === "ADMIN" ? (
                            <Members />
                          ) : (
                            <p role="alert">{t("permissionDenied")}</p>
                          )
                        }
                      />
                      <Route path="/settings" element={<Settings />} />
                      <Route path="/madrasa" element={<Madrasa />} />
                      <Route path="/tuition" element={<Tuition />} />
                      <Route path="/events" element={<Events />} />
                      <Route path="/notices" element={<Notices />} />
                      <Route path="/warnings" element={<Warnings />} />
                      <Route path="/work" element={<Workflows />} />
                      <Route path="/exams" element={<Exams />} />
                      <Route path="/attendance" element={<Attendance />} />
                      <Route path="/students" element={<Students />} />
                      <Route
                        path="/students/:id"
                        element={<StudentProfile />}
                      />
                      <Route
                        path="/setup"
                        element={
                          membership?.role === "ADMIN" ? (
                            <AcademicSetup />
                          ) : (
                            <p role="alert">{t("permissionDenied")}</p>
                          )
                        }
                      />
                      <Route path="/account" element={<Account />} />
                      <Route path="*" element={<Navigate to="/" replace />} />
                    </Routes>
                  )}
                </Suspense>
              </main>
              <nav className="bottomnav" aria-label={t("office")}>
                {!me.data.must_change_password &&
                  menu.map((item) => (
                    <NavLink
                      key={item.path}
                      to={item.path}
                      end={item.path === "/"}
                    >
                      <item.icon size={22} />
                      <span>{t(item.key)}</span>
                    </NavLink>
                  ))}
              </nav>
            </div>
          </div>
        )
      )}
    </>
  );
}
