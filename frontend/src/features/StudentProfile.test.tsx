import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import i18n from "../i18n";
import { api } from "../api";
import { useSession } from "../store";
import StudentProfile from "./StudentProfile";
import type { Role } from "../types";
vi.mock("../api", () => ({ api: vi.fn() }));
vi.mock("../App", () => ({
  useConfig: () => ({
    data: { groups: { primary: "Class", secondary: "Division" } },
  }),
  Loading: () => <div>Loading</div>,
  ErrorState: ({ error }: { error: Error }) => (
    <p role="alert">{error.message}</p>
  ),
}));
function setup(role: Role, manage: boolean) {
  useSession
    .getState()
    .select({
      id: 1,
      institution_id: 1,
      institution_name: "North",
      type: "SCHOOL",
      role,
    });
  vi.mocked(api).mockImplementation(async (path) =>
    path === "/students/1/"
      ? {
          id: 1,
          name: "Amina",
          admission_number: "N001",
          class_group: 1,
          class_group_name: "8",
          division: 1,
          division_name: "A",
          academic_year_name: "2026–27",
          can_manage: manage,
          can_view_guardians: false,
          has_login: false,
          joined_on: "2026-06-01",
        }
      : path.endsWith("/insights/")
        ? {
            attendance: { total: 0, attended: 0, percentage: null, streak: 0 },
            trend: [],
            events: [],
          }
        : { count: 0, next: null, previous: null, results: [] },
  );
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter initialEntries={["/students/1"]}>
        <Routes>
          <Route path="/students/:id" element={<StudentProfile />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
beforeEach(() => {
  void i18n.changeLanguage("en");
});
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  useSession.getState().clear();
});
describe("student profile privacy", () => {
  it("does not render medical entry points or management controls for student roles", async () => {
    setup("STUDENT", false);
    await screen.findByRole("heading", { name: "Amina" });
    expect(
      screen.queryByRole("tab", { name: "Medical emergency card" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Guardians")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Edit" }),
    ).not.toBeInTheDocument();
    expect(screen.getByText("01/06/2026")).toBeInTheDocument();
  });
  it("offers class-teacher controls without offering permanent deletion", async () => {
    setup("TEACHER", true);
    await screen.findByRole("heading", { name: "Amina" });
    expect(
      screen.getByRole("tab", { name: "Medical emergency card" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Archive student" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Delete permanently" }),
    ).not.toBeInTheDocument();
  });
});
