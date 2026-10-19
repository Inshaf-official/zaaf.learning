import { afterEach, expect, it, vi } from "vitest";
import { render, screen, cleanup, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { api } from "../api";
import { useSession } from "../store";
import "../i18n";
import Attendance from "./Attendance";
vi.mock("../api", () => ({
  api: vi.fn(),
  download: vi.fn(),
  ApiError: class extends Error {},
}));
vi.mock("../App", () => ({
  Loading: () => <div>Loading</div>,
  ErrorState: ({ error }: { error: Error }) => (
    <p role="alert">{error.message}</p>
  ),
}));
vi.mock("../lib/offline", () => ({
  pending: async () => [],
  replay: async () => {},
  storePending: async () => {},
  discard: async () => {},
}));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  useSession.getState().clear();
});
it("defaults to present and saves the class in one bulk request", async () => {
  useSession
    .getState()
    .select({
      id: 1,
      institution_id: 1,
      institution_name: "North",
      type: "SCHOOL",
      role: "TEACHER",
    });
  vi.mocked(api).mockImplementation(async (path, options) => {
    if (options?.method === "POST") return [];
    if (path.startsWith("/class-groups"))
      return {
        count: 1,
        next: null,
        previous: null,
        results: [
          { id: 1, name: "8", academic_year: 1, academic_year_name: "2026" },
        ],
      };
    if (path.startsWith("/students"))
      return {
        count: 1,
        next: null,
        previous: null,
        results: [{ id: 1, name: "Amina", can_manage: true }],
      };
    return { count: 0, next: null, previous: null, results: [] };
  });
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <Attendance />
    </QueryClientProvider>,
  );
  const user = userEvent.setup();
  await screen.findByRole("option", { name: "8" });
  await user.selectOptions(screen.getByRole("combobox"), "1");
  await screen.findByRole("button", { name: "Amina: Present" });
  await user.click(screen.getByRole("button", { name: "Amina: Absent" }));
  await user.click(screen.getByRole("button", { name: "Save attendance" }));
  await waitFor(() =>
    expect(
      vi
        .mocked(api)
        .mock.calls.some(
          ([path, options]) =>
            path === "/attendance/bulk/" &&
            JSON.stringify(options?.body).includes("ABSENT"),
        ),
    ).toBe(true),
  );
});
