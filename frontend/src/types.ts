export type Role = "ADMIN" | "TEACHER" | "PARENT" | "STUDENT";
export type InstitutionType = "SCHOOL" | "TUITION" | "MADRASA";
export interface Membership {
  config?: InstitutionConfig;
  id: number;
  institution_id: number;
  institution_name: string;
  type: InstitutionType;
  role: Role;
}
export interface User {
  id: number;
  name: string;
  email: string | null;
  login_id: string | null;
  must_change_password: boolean;
  memberships: Membership[];
}
export interface InstitutionConfig {
  id: number;
  name: string;
  type: InstitutionType;
  role: Role;
  label: string;
  roles: Partial<Record<Role, string>>;
  groups: { primary: string; secondary: string };
  attendance_mode: string;
  modules: string[];
}
export interface Member {
  id: number;
  user_id: number;
  name: string;
  email: string | null;
  login_id: string | null;
  role: Role;
  is_active: boolean;
  must_change_password: boolean;
}
export interface Page<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
export interface Session {
  user?: User;
  access: string;
  must_change_password: boolean;
}
export interface InviteResult {
  member: Member;
  temporary_password?: string;
}

export interface Credential {
  identity: string;
  temporary_password?: string;
}
export interface EmergencyStudent {
  id: number;
  name: string;
  admission_number: string;
}
export interface Student extends EmergencyStudent {
  class_group: number;
  class_group_name: string;
  division: number | null;
  division_name: string | null;
  academic_year_name: string;
  can_manage: boolean;
  can_view_guardians: boolean;
  has_login: boolean;
}
export interface Guardian {
  id: number;
  name: string;
  email: string;
  phone: string;
  relationship: string;
}
export interface StudentDetail extends Student {
  interest_tags?: string[];
  date_of_birth?: string | null;
  joined_on: string;
  guardians?: Guardian[];
}
export interface StudentMutation {
  student: StudentDetail;
  credentials: Credential[];
}
export interface Capabilities {
  can_create: boolean;
  can_emergency_lookup: boolean;
}
export interface EmergencyContact {
  name: string;
  relationship: string;
  phone: string;
}
export interface MedicalRecord {
  blood_group: string;
  allergies: string;
  conditions: string;
  doctor: string;
  emergency_contacts: EmergencyContact[];
  updated_at: string;
}
export interface MedicalResponse {
  student_id: number;
  student_name: string;
  can_edit: boolean;
  access_expires_at: string | null;
  card: MedicalRecord | null;
}
export interface Grant {
  id: number;
  reason: string;
  granted_at: string;
  expires_at: string;
}
export interface Notification {
  id: number;
  title: string;
  body: string;
  kind: string;
  student: number | null;
  created_at: string;
  read_at: string | null;
}
