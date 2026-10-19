import { create } from "zustand";
import type { Membership } from "./types";
interface SessionStore {
  access: string | null;
  membership: Membership | null;
  setAccess: (access: string | null) => void;
  select: (membership: Membership | null) => void;
  clear: () => void;
}
export const useSession = create<SessionStore>((set) => ({
  access: null,
  membership: null,
  setAccess: (access) => set({ access }),
  select: (membership) => set({ membership }),
  clear: () => set({ access: null, membership: null }),
}));
export function useCan(
  action:
    | "members.manage"
    | "account.manage"
    | "academic.manage"
    | "medical.emergency",
): boolean {
  const role = useSession((s) => s.membership?.role);
  if (action === "account.manage") return Boolean(role);
  if (action === "medical.emergency") return role === "TEACHER";
  return role === "ADMIN";
}
