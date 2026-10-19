import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import i18n from "../i18n";
import { api, ApiError } from "../api";
import { useSession } from "../store";
import MedicalCard from "./MedicalCard";
vi.mock("../api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api")>()),
  api: vi.fn(),
}));
vi.mock("../App", () => ({
  Loading: () => <div>Loading</div>,
  ErrorState: ({ error }: { error: Error }) => (
    <p role="alert">{error.message}</p>
  ),
}));
beforeEach(() => {
  void i18n.changeLanguage("en");
  useSession
    .getState()
    .select({
      id: 1,
      institution_id: 1,
      institution_name: "North",
      type: "SCHOOL",
      role: "TEACHER",
    });
});
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  useSession.getState().clear();
});
function renderCard() {
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MedicalCard studentId={1} />
    </QueryClientProvider>,
  );
}
describe("emergency medical access", () => {
  it("requires a reason before granting temporary read-only access", async () => {
    let unlocked = false;
    vi.mocked(api).mockImplementation(async (path) => {
      if (path.endsWith("/break-glass/")) {
        unlocked = true;
        return {
          id: 1,
          reason: "Breathing difficulty",
          granted_at: new Date().toISOString(),
          expires_at: new Date(Date.now() + 1800000).toISOString(),
        };
      }
      if (!unlocked) throw new ApiError(403, "Medical access denied");
      return {
        student_id: 1,
        student_name: "Amina",
        can_edit: false,
        access_expires_at: new Date(Date.now() + 1800000).toISOString(),
        card: {
          blood_group: "O+",
          allergies: "Penicillin",
          conditions: "Asthma",
          doctor: "Dr Rao",
          updated_at: new Date().toISOString(),
          emergency_contacts: [
            {
              name: "Guardian",
              phone: "+919876543210",
              relationship: "Parent",
            },
          ],
        },
      };
    });
    renderCard();
    await screen.findByText("Medical information is restricted");
    const button = screen.getByRole("button", {
      name: "Unlock for 30 minutes",
    });
    expect(button).toBeDisabled();
    const user = userEvent.setup();
    await user.type(
      screen.getByLabelText("Reason for emergency access"),
      "Student is having breathing difficulty",
    );
    await user.click(button);
    expect(await screen.findByText("Penicillin")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "+919876543210" })).toHaveAttribute(
      "href",
      "tel:+919876543210",
    );
    expect(
      screen.queryByRole("button", { name: "Edit" }),
    ).not.toBeInTheDocument();
    expect(api).toHaveBeenCalledWith("/students/1/break-glass/", {
      method: "POST",
      body: { reason: "Student is having breathing difficulty" },
    });
  });
});
