import { useQuery } from "@tanstack/react-query";
import { z } from "zod";
import { api } from "../api";
import { useSession } from "../store";
import type { Page } from "../types";
export interface AcademicYear {
  id: number;
  name: string;
  starts_on: string;
  ends_on: string;
  is_current: boolean;
}
export interface ClassGroup {
  id: number;
  name: string;
  academic_year: number;
  academic_year_name: string;
}
export interface Division {
  id: number;
  name: string;
  class_group: number;
  class_group_name: string;
}
export interface Subject {
  id: number;
  name: string;
  code: string;
}
export interface Teacher {
  id: number;
  user_id: number;
  name: string;
}
export interface Assignment {
  id: number;
  teacher: number;
  teacher_name: string;
  class_group: number;
  class_group_name: string;
  division: number | null;
  division_name: string | null;
  subject: number | null;
  subject_name: string | null;
  is_class_teacher: boolean;
}
export async function allPages<T>(path: string): Promise<T[]> {
  const result: T[] = [];
  let page = 1;
  for (;;) {
    const data = await api<Page<T>>(
      `${path}${path.includes("?") ? "&" : "?"}page=${page}`,
    );
    result.push(...data.results);
    if (!data.next) return result;
    page++;
  }
}
export function useOptions<T>(resource: string, enabled = true) {
  const member = useSession((s) => s.membership);
  return useQuery({
    queryKey: ["options", resource, member?.id],
    queryFn: () => allPages<T>(`/${resource}/`),
    enabled: Boolean(member) && enabled,
  });
}
export const studentSchema = z.object({
  name: z.string().trim().min(1).max(150),
  admission_number: z.string().trim().min(1).max(100),
  class_group: z.string().min(1),
  division: z.string(),
  date_of_birth: z.string(),
  joined_on: z.string().min(1),
});
export type StudentFields = z.infer<typeof studentSchema>;
export const guardianSchema = z.object({
  name: z.string().trim().min(1).max(150),
  email: z.string().email(),
  phone: z.string().regex(/^$|^\+?[0-9 ()-]{6,25}$/),
  relationship: z.string().trim().min(1).max(50),
  delivery: z.enum(["temporary", "email"]),
});
export type GuardianFields = z.infer<typeof guardianSchema>;
export function studentPayload(fields: StudentFields) {
  return {
    ...fields,
    class_group: Number(fields.class_group),
    division: fields.division ? Number(fields.division) : null,
    date_of_birth: fields.date_of_birth || null,
  };
}
export function indianDate(value: string): string {
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: "Asia/Kolkata",
  }).format(new Date(value.length === 10 ? value + "T00:00:00+05:30" : value));
}
export function localToday(): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    timeZone: "Asia/Kolkata",
  }).formatToParts(new Date());
  const get = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((p) => p.type === type)?.value || "";
  return `${get("year")}-${get("month")}-${get("day")}`;
}
