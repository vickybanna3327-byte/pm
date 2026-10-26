import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuthGate } from "@/components/AuthGate";

describe("AuthGate", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it("requires sign-in before showing the board", async () => {
    render(<AuthGate />);

    expect(
      await screen.findByRole("heading", { name: "Sign in to Kanban Studio" })
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Kanban Studio" })
    ).not.toBeInTheDocument();
  });

  it("rejects incorrect credentials and keeps the board gated", async () => {
    const user = userEvent.setup();
    render(<AuthGate />);

    await screen.findByRole("heading", { name: "Sign in to Kanban Studio" });
    await user.type(screen.getByLabelText("Username"), "user");
    await user.type(screen.getByLabelText("Password"), "wrong");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Incorrect username or password."
    );
    expect(
      screen.queryByRole("heading", { name: "Kanban Studio" })
    ).not.toBeInTheDocument();
    expect(sessionStorage.getItem("pm-mvp-authenticated")).toBeNull();
  });

  it("signs in with the required credentials and keeps the session in this tab", async () => {
    const user = userEvent.setup();
    const { unmount } = render(<AuthGate />);

    await screen.findByRole("heading", { name: "Sign in to Kanban Studio" });
    await user.type(screen.getByLabelText("Username"), "user");
    await user.type(screen.getByLabelText("Password"), "password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(
      await screen.findByRole("heading", { name: "Kanban Studio" })
    ).toBeInTheDocument();
    expect(sessionStorage.getItem("pm-mvp-authenticated")).toBe("true");

    unmount();
    render(<AuthGate />);
    expect(
      await screen.findByRole("heading", { name: "Kanban Studio" })
    ).toBeInTheDocument();
  });

  it("logs out and clears the signed-in session", async () => {
    const user = userEvent.setup();
    sessionStorage.setItem("pm-mvp-authenticated", "true");
    render(<AuthGate />);

    await screen.findByRole("heading", { name: "Kanban Studio" });
    await user.click(screen.getByRole("button", { name: "Log out" }));

    expect(
      await screen.findByRole("heading", { name: "Sign in to Kanban Studio" })
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(sessionStorage.getItem("pm-mvp-authenticated")).toBeNull()
    );
  });
});
