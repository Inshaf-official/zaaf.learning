import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "../i18n";
import Login from "./Login";
import { api } from "../api";
import { useSession } from "../store";
vi.mock("../api", () => ({ api: vi.fn() }));
function setup() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return userEvent.setup();
}
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  useSession.getState().clear();
});
describe("invite-only login", () => {
  it("validates required identity before making a request", async () => {
    const user = setup();
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findAllByText("This field is required.")).toHaveLength(
      2,
    );
    expect(api).not.toHaveBeenCalled();
  });
  it("submits login ID and keeps access only in memory", async () => {
    vi.mocked(api).mockResolvedValue({
      access: "test-access",
      must_change_password: false,
    });
    const user = setup();
    await user.type(screen.getByLabelText("Email or login ID"), "school-001");
    await user.type(screen.getByLabelText("Password"), "correct-password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(api).toHaveBeenCalledWith("/auth/login/", {
      method: "POST",
      body: { identifier: "school-001", password: "correct-password" },
      anonymous: true,
    });
    expect(useSession.getState().access).toBe("test-access");
    expect(localStorage.getItem("access")).toBeNull();
  });
  it("shows authentication errors", async () => {
    vi.mocked(api).mockRejectedValue(new Error("Unable to sign in."));
    const user = setup();
    await user.type(screen.getByLabelText("Email or login ID"), "unknown");
    await user.type(screen.getByLabelText("Password"), "wrong");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Unable to sign in.",
    );
  });
});
