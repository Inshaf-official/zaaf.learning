import { useState, useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import { useSession } from "../store";
import { useOptions, allPages, indianDate } from "../lib/student-forms";
import type { ClassGroup, Subject } from "../lib/student-forms";
import type { Student, Page } from "../types";
import { Loading, ErrorState } from "../App";
import { Sheet } from "./StudentForms";
import EntityForm from "./EntityForm";
import Roster from "./Roster";
interface Fee {
  id: number;
  student_name: string;
  label: string;
  amount: string;
  paid_amount: string;
  due_date: string;
}
interface Series {
  id: number;
  name: string;
  class_group: number;
  max_marks: string;
  published: boolean;
}
interface Rank {
  student: number;
  name: string;
  score: string;
  maximum: string;
  rank: number;
}
interface Result {
  student: number;
  score: string;
}
interface Performance {
  series__class_group__name: string;
  series__name: string;
  average: number;
}
export default function Tuition() {
  const { t } = useTranslation();
  const member = useSession((s) => s.membership);
  const admin = member?.role === "ADMIN";
  const staff = admin || member?.role === "TEACHER";
  const client = useQueryClient();
  const [tab, setTab] = useState<"fees" | "tests">("fees");
  const [open, setOpen] = useState<"fee" | "payment" | "series" | null>(null);
  const [payment, setPayment] = useState<Fee | null>(null);
  const [seriesId, setSeriesId] = useState("");
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");
  const [scores, setScores] = useState<Record<number, string>>({});
  const students = useOptions<Student>("students");
  const groups = useOptions<ClassGroup>("class-groups");
  const subjects = useOptions<Subject>("subjects");
  const series = useOptions<Series>("test-series");
  const chosen = series.data?.find((s) => String(s.id) === seriesId);
  const roster =
    students.data?.filter((s) => s.class_group === chosen?.class_group) || [];
  const fees = useQuery({
    queryKey: ["fees", member?.id, page],
    queryFn: () => api<Page<Fee>>(`/fees/?page=${page}`),
  });
  const results = useQuery({
    queryKey: ["test-results", member?.id, seriesId],
    enabled: !!seriesId,
    queryFn: () => allPages<Result>(`/test-results/?series=${seriesId}`),
  });
  const ranks = useQuery({
    queryKey: ["ranks", member?.id, seriesId, page],
    enabled: !!seriesId,
    queryFn: () =>
      api<Page<Rank>>(`/test-series/${seriesId}/ranks/?page=${page}`),
  });
  const performance = useQuery({
    queryKey: ["batch-performance", member?.id],
    enabled: staff,
    queryFn: () => api<Page<Performance>>("/test-series/performance/"),
  });
  useEffect(() => {
    setScores(
      Object.fromEntries((results.data || []).map((r) => [r.student, r.score])),
    );
  }, [results.data]);
  async function mutate(path: string, body: unknown) {
    try {
      await api(path, { method: "POST", body });
      setOpen(null);
      setError("");
      await client.invalidateQueries();
    } catch (e) {
      setError(String(e));
    }
  }
  return (
    <>
      <h1>{t("tuitionManagement")}</h1>
      <div className="profile-tabs">
        <button aria-pressed={tab === "fees"} onClick={() => setTab("fees")}>
          {t("fees")}
        </button>
        <button aria-pressed={tab === "tests"} onClick={() => setTab("tests")}>
          {t("tests")}
        </button>
      </div>
      {tab === "fees" ? (
        <section className="panel">
          <h2>{t("feeInstallments")}</h2>
          {admin && (
            <button className="primary" onClick={() => setOpen("fee")}>
              {t("addInstallment")}
            </button>
          )}
          {fees.isPending ? (
            <Loading />
          ) : fees.error ? (
            <ErrorState error={fees.error} retry={() => void fees.refetch()} />
          ) : (
            <>
              <ul className="people">
                {fees.data.results.map((fee) => (
                  <li key={fee.id}>
                    <div>
                      <strong>
                        {fee.student_name} · {fee.label}
                      </strong>
                      <span>{indianDate(fee.due_date)}</span>
                      <span>
                        {new Intl.NumberFormat("en-IN", {
                          style: "currency",
                          currency: "INR",
                        }).format(
                          Number(fee.amount) - Number(fee.paid_amount),
                        )}{" "}
                        {t("outstanding")}
                      </span>
                    </div>
                    {admin && (
                      <div className="row-actions">
                        <button
                          onClick={() => {
                            setPayment(fee);
                            setOpen("payment");
                          }}
                        >
                          {t("recordPayment")}
                        </button>
                        <button
                          onClick={() =>
                            void mutate(`/fees/${fee.id}/remind/`, {})
                          }
                        >
                          {t("sendReminder")}
                        </button>
                      </div>
                    )}
                  </li>
                ))}
              </ul>
              <div className="pagination">
                <button
                  disabled={!fees.data.previous}
                  onClick={() => setPage(page - 1)}
                >
                  {t("previous")}
                </button>
                <button
                  disabled={!fees.data.next}
                  onClick={() => setPage(page + 1)}
                >
                  {t("next")}
                </button>
              </div>
            </>
          )}
        </section>
      ) : (
        <>
          <section className="panel">
            {staff && (
              <button className="primary" onClick={() => setOpen("series")}>
                {t("createTest")}
              </button>
            )}
            <label>
              {t("testSeries")}
              <select
                value={seriesId}
                onChange={(e) => {
                  setSeriesId(e.target.value);
                  setPage(1);
                }}
              >
                <option value="">{t("choose")}</option>
                {series.data?.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} · {t(s.published ? "published" : "draft")}
                  </option>
                ))}
              </select>
            </label>
            {staff && chosen && (
              <>
                <Roster
                  count={roster.length}
                  row={(index) => {
                    const student = roster[index];
                    return (
                      <div className="attendance-row">
                        <label>
                          {student.name}
                          <input
                            type="number"
                            inputMode="decimal"
                            min={0}
                            max={chosen.max_marks}
                            value={scores[student.id] || ""}
                            disabled={chosen.published}
                            onChange={(e) =>
                              setScores((old) => ({
                                ...old,
                                [student.id]: e.target.value,
                              }))
                            }
                          />
                        </label>
                      </div>
                    );
                  }}
                />
                <button
                  className="primary"
                  disabled={chosen.published}
                  onClick={() =>
                    void mutate("/test-results/bulk/", {
                      series: Number(seriesId),
                      rows: roster.map((s) => ({
                        student: s.id,
                        score: scores[s.id] || "",
                      })),
                    })
                  }
                >
                  {t("saveMarks")}
                </button>
                <button
                  onClick={() =>
                    void mutate(`/test-series/${seriesId}/publication/`, {
                      published: !chosen.published,
                    })
                  }
                >
                  {t(chosen.published ? "unpublish" : "publish")}
                </button>
              </>
            )}
          </section>
          {seriesId && (
            <section className="panel">
              <h2>{t("rankList")}</h2>
              <ul className="people">
                {ranks.data?.results.map((rank) => (
                  <li key={rank.student}>
                    <span className="rank-badge">{rank.rank}</span>
                    <strong>{rank.name}</strong>
                    <span>
                      {rank.score}/{rank.maximum}
                    </span>
                  </li>
                ))}
              </ul>
              <div className="pagination">
                <button
                  disabled={!ranks.data?.previous}
                  onClick={() => setPage(page - 1)}
                >
                  {t("previous")}
                </button>
                <button
                  disabled={!ranks.data?.next}
                  onClick={() => setPage(page + 1)}
                >
                  {t("next")}
                </button>
              </div>
            </section>
          )}
          {staff && (
            <section className="panel">
              <h2>{t("batchPerformance")}</h2>
              <ul className="people">
                {performance.data?.results.map((row, index) => (
                  <li key={index}>
                    <strong>
                      {row.series__class_group__name} · {row.series__name}
                    </strong>
                    <span>{Number(row.average).toFixed(1)}%</span>
                    <progress
                      aria-label={
                        row.series__class_group__name + " " + row.series__name
                      }
                      value={Number(row.average)}
                      max={100}
                    />
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <Sheet
        open={!!open}
        onOpenChange={() => setOpen(null)}
        title={t(
          open === "fee"
            ? "addInstallment"
            : open === "payment"
              ? "recordPayment"
              : "createTest",
        )}
        description={t("tuitionHelp")}
      >
        {open === "fee" ? (
          <EntityForm
            fields={[
              {
                name: "student",
                label: t("student"),
                type: "select",
                required: true,
                options: students.data?.map((s) => ({
                  value: String(s.id),
                  label: s.name,
                })),
              },
              { name: "label", label: t("label"), required: true },
              {
                name: "amount",
                label: t("amount"),
                type: "number",
                min: 0.01,
                required: true,
              },
              {
                name: "due_date",
                label: t("dueDate"),
                type: "date",
                required: true,
              },
            ]}
            onSubmit={(data) =>
              mutate("/fees/", { ...data, student: Number(data.student) })
            }
          />
        ) : open === "payment" ? (
          <EntityForm
            fields={[
              {
                name: "amount",
                label: t("amount"),
                type: "number",
                min: 0.01,
                max: payment
                  ? Number(payment.amount) - Number(payment.paid_amount)
                  : 0,
                required: true,
              },
              {
                name: "reference",
                label: t("paymentReference"),
                required: true,
              },
            ]}
            onSubmit={(data) => mutate(`/fees/${payment?.id}/payment/`, data)}
          />
        ) : (
          <EntityForm
            fields={[
              { name: "name", label: t("recordName"), required: true },
              {
                name: "class_group",
                label: t("batch"),
                type: "select",
                required: true,
                options: groups.data?.map((g) => ({
                  value: String(g.id),
                  label: g.name,
                })),
              },
              {
                name: "subject",
                label: t("subject"),
                type: "select",
                required: true,
                options: subjects.data?.map((s) => ({
                  value: String(s.id),
                  label: s.name,
                })),
              },
              { name: "date", label: t("date"), type: "date", required: true },
              {
                name: "max_marks",
                label: t("maximumMarks"),
                type: "number",
                min: 0.01,
                required: true,
              },
            ]}
            onSubmit={(data) =>
              mutate("/test-series/", {
                ...data,
                class_group: Number(data.class_group),
                subject: Number(data.subject),
              })
            }
          />
        )}{" "}
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
      </Sheet>
    </>
  );
}
