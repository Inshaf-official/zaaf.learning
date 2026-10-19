import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import i18n from "../i18n";
import { api } from "../api";
import { useSession } from "../store";
import Students from "./Students";
vi.mock("../api", () => ({ api: vi.fn() }));
vi.mock("../App", () => ({
  useConfig: () => ({
    data: {
      name: "North School",
      groups: { primary: "Class", secondary: "Division" },
    },
  }),
  Loading: () => <div>Loading</div>,
  ErrorState: ({ error }: { error: Error }) => (
    <p role="alert">{error.message}</p>
  ),
}));
const student = {
  id: 1,
  name: "Amina",
  admission_number: "N001",
  class_group: 1,
  class_group_name: "8",
  division: 1,
  division_name: "A",
  academic_year_name: "2026–27",
  can_manage: false,
  can_view_guardians: false,
  has_login: false,
};
function setup(create = false, emergency = false) {
  useSession
    .getState()
    .select({
      id: 1,
      institution_id: 1,
      institution_name: "North",
      type: "SCHOOL",
      role: create ? "TEACHER" : "PARENT",
    });
  vi.mocked(api).mockImplementation(async (path) => {
    if (path.includes("/capabilities/"))
      return { can_create: create, can_emergency_lookup: emergency };
    if (path.startsWith("/class-groups/"))
      return {
        count: 1,
        next: null,
        previous: null,
        results: [
          { id: 1, name: "8", academic_year: 1, academic_year_name: "2026–27" },
        ],
      };
    if (path.startsWith("/divisions/"))
      return {
        count: 1,
        next: null,
        previous: null,
        results: [{ id: 1, name: "A", class_group: 1, class_group_name: "8" }],
      };
    if (path.startsWith("/medical/directory/"))
      return { count: 0, next: null, previous: null, results: [] };
    return { count: 1, next: null, previous: null, results: [student] };
  });
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter>
        <Students />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return userEvent.setup();
}
beforeEach(() => {
  void i18n.changeLanguage("en");
});
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  useSession.getState().clear();
});
describe("student search", () => {
  it("debounces input and sends the expected search parameter", async () => {
    const user = setup();
    expect(await screen.findByRole("link", { name: /Amina/ })).toHaveAttribute(
      "href",
      "/students/1",
    );
    await user.type(screen.getByLabelText("Search students"), "Amina");
    await waitFor(() =>
      expect(
        vi
          .mocked(api)
          .mock.calls.some(([path]) => path.includes("search=Amina")),
      ).toBe(true),
    );
    expect(
      screen.queryByRole("button", { name: "Add student" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByLabelText("Emergency search across the institution"),
    ).not.toBeInTheDocument();
  });
  it("offers creation to class teachers and emergency search to staff", async () => {
    const user = setup(true, true);
    await screen.findByRole("button", { name: "Add student" });
    await user.click(screen.getByLabelText(/Emergency search across/));
    await waitFor(() =>
      expect(
        vi
          .mocked(api)
          .mock.calls.some(([path]) => path.startsWith("/medical/directory/")),
      ).toBe(true),
    );
    expect(await screen.findByText("No students found")).toBeInTheDocument();
  });
});
