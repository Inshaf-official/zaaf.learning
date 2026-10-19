import { useState, useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api, download } from "../api";
import { useSession } from "../store";
import { allPages, useOptions } from "../lib/student-forms";
import type { ClassGroup, Subject } from "../lib/student-forms";
import type { Student, Page } from "../types";
import { Loading, ErrorState } from "../App";
import { Sheet } from "./StudentForms";
import EntityForm from "./EntityForm";
import Roster from "./Roster";
interface ExamSubject {
  id: number;
  subject_name: string;
  max_marks: string;
}
interface Exam {
  id: number;
  name: string;
  class_group: number;
  class_group_name: string;
  date: string;
  published: boolean;
  exam_subjects: ExamSubject[];
}
interface Mark {
  student: number;
  student_name: string;
  score: string;
  absent: boolean;
  subject_name: string;
  max_marks: string;
  grade?: string;
}
interface Hold {
  id: number;
  student: number;
  exam: number;
  student_name: string;
  released_at: string | null;
  note: string;
}
export default function Exams() {
  const { t } = useTranslation();
  const member = useSession((s) => s.membership);
  const admin = member?.role === "ADMIN";
  const staff = admin || member?.role === "TEACHER";
  const client = useQueryClient();
  const [examId, setExamId] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [studentId, setStudentId] = useState("");
  const [open, setOpen] = useState<"exam" | "subject" | "hold" | null>(null);
  const [error, setError] = useState("");
  const [scores, setScores] = useState<
    Record<number, { score: string; absent: boolean }>
  >({});
  const [busy, setBusy] = useState(false);
  const exams = useOptions<Exam>("exams");
  const groups = useOptions<ClassGroup>("class-groups");
  const subjects = useOptions<Subject>("subjects");
  const exam = exams.data?.find((e) => String(e.id) === examId);
  const students = useQuery({
    queryKey: ["exam-students", member?.id, exam?.class_group],
    enabled: !!exam,
    queryFn: () =>
      allPages<Student>(`/students/?class_group=${exam!.class_group}`),
  });
  const marks = useQuery({
    queryKey: ["marks", member?.id, subjectId],
    enabled: !!subjectId && staff,
    queryFn: () => allPages<Mark>(`/marks/?exam_subject=${subjectId}`),
  });
  const result = useQuery({
    queryKey: ["result", member?.id, examId, studentId],
    enabled: !!examId && !!studentId,
    queryFn: () =>
      api<{ held: boolean; message?: string; marks: Mark[] }>(
        `/exams/${examId}/result/?student=${studentId}`,
      ),
  });
  const holds = useQuery({
    queryKey: ["holds", member?.id, examId],
    enabled: admin && !!examId,
    queryFn: () => api<Page<Hold>>(`/holds/?exam=${examId}`),
  });
  useEffect(() => {
    setScores(
      Object.fromEntries(
        students.data?.map((student) => {
          const mark = marks.data?.find((m) => m.student === student.id);
          return [
            student.id,
            { score: mark?.score || "", absent: mark?.absent || false },
          ];
        }) || [],
      ),
    );
  }, [students.data, marks.data]);
  async function mutate(path: string, body: unknown) {
    setError("");
    try {
      await api(path, { method: "POST", body });
      setOpen(null);
      await client.invalidateQueries();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("retry"));
    }
  }
  async function save() {
    if (!subjectId) return;
    setBusy(true);
    try {
      await mutate("/marks/bulk/", {
        exam_subject: Number(subjectId),
        rows: Object.entries(scores).map(([student, value]) => ({
          student: Number(student),
          score: value.absent ? "0" : value.score,
          absent: value.absent,
        })),
      });
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <h1>{t("exams")}</h1>
      {admin && (
        <button className="primary" onClick={() => setOpen("exam")}>
          {t("createExam")}
        </button>
      )}
      <section className="panel">
        <label>
          {t("exam")}
          <select
            value={examId}
            onChange={(e) => {
              setExamId(e.target.value);
              setSubjectId("");
              setStudentId("");
            }}
          >
            <option value="">{t("choose")}</option>
            {exams.data?.map((e) => (
              <option key={e.id} value={e.id}>
                {e.name} · {e.class_group_name}
                {e.published ? "" : " · " + t("draft")}
              </option>
            ))}
          </select>
        </label>
        {exam && (
          <>
            <p>{t(exam.published ? "published" : "draft")}</p>
            {admin && (
              <div className="row-actions">
                <button onClick={() => setOpen("subject")}>
                  {t("addExamSubject")}
                </button>
                <button
                  onClick={() =>
                    void mutate(`/exams/${exam.id}/publication/`, {
                      published: !exam.published,
                    })
                  }
                >
                  {t(exam.published ? "unpublish" : "publish")}
                </button>
                <button onClick={() => setOpen("hold")}>
                  {t("holdMarks")}
                </button>
                <button
                  onClick={() =>
                    void download(
                      `/exams/${exam.id}/report/`,
                      "class-reports.pdf",
                    ).catch((e) => setError(String(e)))
                  }
                >
                  {t("classReports")}
                </button>
              </div>
            )}
          </>
        )}
      </section>
      {exam && staff && (
        <section className="panel">
          <label>
            {t("subject")}
            <select
              value={subjectId}
              onChange={(e) => setSubjectId(e.target.value)}
            >
              <option value="">{t("choose")}</option>
              {exam.exam_subjects.map((subject) => (
                <option key={subject.id} value={subject.id}>
                  {subject.subject_name} / {subject.max_marks}
                </option>
              ))}
            </select>
          </label>
          {subjectId &&
            (students.isPending || marks.isPending ? (
              <Loading />
            ) : students.error || marks.error ? (
              <ErrorState
                error={(students.error || marks.error)!}
                retry={() => {
                  void students.refetch();
                  void marks.refetch();
                }}
              />
            ) : (
              <>
                <Roster
                  count={students.data?.length || 0}
                  row={(index) => {
                    const student = students.data![index];
                    return (
                      <div className="attendance-row">
                        <strong>{student.name}</strong>
                        <div className="filter-grid">
                          <label>
                            {t("score")}
                            <input
                              type="number"
                              inputMode="decimal"
                              min={0}
                              max={
                                exam.exam_subjects.find(
                                  (s) => String(s.id) === subjectId,
                                )?.max_marks
                              }
                              step="0.01"
                              value={scores[student.id]?.score || ""}
                              disabled={
                                exam.published || scores[student.id]?.absent
                              }
                              onChange={(e) =>
                                setScores((previous) => ({
                                  ...previous,
                                  [student.id]: {
                                    ...previous[student.id],
                                    score: e.target.value,
                                  },
                                }))
                              }
                            />
                          </label>
                          <label className="check">
                            <input
                              type="checkbox"
                              checked={scores[student.id]?.absent || false}
                              disabled={exam.published}
                              onChange={(e) =>
                                setScores((previous) => ({
                                  ...previous,
                                  [student.id]: {
                                    score: e.target.checked
                                      ? "0"
                                      : previous[student.id]?.score || "",
                                    absent: e.target.checked,
                                  },
                                }))
                              }
                            />
                            {t("absent")}
                          </label>
                        </div>
                      </div>
                    );
                  }}
                />
                <div className="sticky-action">
                  <button
                    className="primary"
                    disabled={busy || exam.published}
                    onClick={() => void save()}
                  >
                    {t("saveMarks")}
                  </button>
                </div>
              </>
            ))}
        </section>
      )}
      {exam && (
        <section className="panel">
          <h2>{t("reportCards")}</h2>
          <label>
            {t("student")}
            <select
              value={studentId}
              onChange={(e) => setStudentId(e.target.value)}
            >
              <option value="">{t("choose")}</option>
              {students.data?.map((student) => (
                <option key={student.id} value={student.id}>
                  {student.name}
                </option>
              ))}
            </select>
          </label>
          {studentId &&
            (result.isPending ? (
              <Loading />
            ) : result.error ? (
              <ErrorState
                error={result.error}
                retry={() => void result.refetch()}
              />
            ) : result.data?.held ? (
              <p className="notice">{t("heldMessage")}</p>
            ) : (
              <>
                <ul className="people">
                  {result.data?.marks.map((mark) => (
                    <li key={mark.subject_name}>
                      <strong>{mark.subject_name}</strong>
                      <span>
                        {mark.absent ? t("absent") : mark.score} /{" "}
                        {mark.max_marks} · {mark.grade}
                      </span>
                    </li>
                  ))}
                </ul>
                <button
                  onClick={() =>
                    void download(
                      `/exams/${exam.id}/report/?student=${studentId}`,
                      "report-card.pdf",
                    ).catch((e) => setError(String(e)))
                  }
                >
                  {t("downloadReport")}
                </button>
              </>
            ))}
        </section>
      )}
      {admin && holds.data && (
        <section className="panel">
          <h2>{t("markHolds")}</h2>
          <ul className="people">
            {holds.data.results.map((hold) => (
              <li key={hold.id}>
                <strong>{hold.student_name}</strong>
                <span>{hold.note}</span>
                {!hold.released_at && (
                  <button
                    onClick={() =>
                      void mutate(`/holds/${hold.id}/release/`, {})
                    }
                  >
                    {t("release")}
                  </button>
                )}
              </li>
            ))}
          </ul>
        </section>
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
          open === "exam"
            ? "createExam"
            : open === "subject"
              ? "addExamSubject"
              : "holdMarks",
        )}
        description={t("examHelp")}
      >
        {open === "exam" ? (
          <EntityForm
            fields={[
              { name: "name", label: t("recordName"), required: true },
              {
                name: "class_group",
                label: t("class"),
                type: "select",
                required: true,
                options: groups.data?.map((g) => ({
                  value: String(g.id),
                  label: g.name,
                })),
              },
              { name: "date", label: t("date"), type: "date", required: true },
            ]}
            onSubmit={(data) =>
              mutate("/exams/", {
                ...data,
                class_group: Number(data.class_group),
              })
            }
          />
        ) : open === "subject" ? (
          <EntityForm
            fields={[
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
              {
                name: "max_marks",
                label: t("maximumMarks"),
                type: "number",
                min: 0.01,
                required: true,
              },
            ]}
            onSubmit={(data) =>
              mutate("/exam-subjects/", {
                ...data,
                subject: Number(data.subject),
                exam: Number(examId),
              })
            }
          />
        ) : open === "hold" ? (
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
              {
                name: "reason_type",
                label: t("reason"),
                type: "select",
                required: true,
                options: ["FEES", "DISCIPLINE", "DOCUMENTS", "OTHER"].map(
                  (value) => ({ value, label: t(value.toLowerCase()) }),
                ),
              },
              {
                name: "note",
                label: t("note"),
                type: "textarea",
                required: true,
              },
            ]}
            onSubmit={(data) =>
              mutate("/holds/", {
                ...data,
                student: Number(data.student),
                exam: Number(examId),
              })
            }
          />
        ) : null}
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
      </Sheet>
    </>
  );
}
