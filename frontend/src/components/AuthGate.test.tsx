import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuthGate } from "@/components/AuthGate";

const authMocks = vi.hoisted(() => {
  class MockAuthApiError extends Error {
    constructor(
      message: string,
      readonly status: number
    ) {
      super(message);
    }
  }
  return {
    AuthApiError: MockAuthApiError,
    getCurrentUser: vi.fn(),
    login: vi.fn(),
    logout: vi.fn(),
    registerAccount: vi.fn(),
  };
});

vi.mock("@/lib/authApi", () => authMocks);

vi.mock("@/components/ProjectDashboard", () => ({
  ProjectDashboard: ({
    onLogout,
    currentUser,
  }: {
    onLogout: () => void;
    currentUser: { username: string };
  }) => (
    <main>
      <h1>Kanban Studio</h1>
      <p>{currentUser.username}</p>
      <button onClick={onLogout}>Log out</button>
    </main>
  ),
}));

const testUser = {
  id: "user-1",
  username: "testuser",
  email: "test@example.com",
  full_name: "Test User",
  role: "member",
};

describe("AuthGate", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authMocks.getCurrentUser.mockRejectedValue(
      new authMocks.AuthApiError("Authentication required.", 401)
    );
    authMocks.login.mockResolvedValue({ user: testUser });
    authMocks.registerAccount.mockResolvedValue({ message: "Account created." });
  });

  it("shows sign-in until the backend confirms a session", async () => {
    render(<AuthGate />);

    expect(
      await screen.findByRole("heading", { name: "Sign in to Kanban Studio" })
    ).toBeInTheDocument();
    expect(authMocks.getCurrentUser).toHaveBeenCalledOnce();
    expect(
      screen.queryByRole("heading", { name: "Kanban Studio" })
    ).not.toBeInTheDocument();
  });

  it("logs in with username and delegates logout to the backend", async () => {
    const user = userEvent.setup();
    render(<AuthGate />);

    await screen.findByRole("heading", { name: "Sign in to Kanban Studio" });
    await user.type(screen.getByLabelText("Username"), "testuser");
    await user.type(screen.getByLabelText("Password"), "password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("heading", { name: "Kanban Studio" }))
      .toBeInTheDocument();
    expect(authMocks.login).toHaveBeenCalledWith("testuser", "password");

    authMocks.logout.mockResolvedValue(undefined);
    await user.click(screen.getByRole("button", { name: "Log out" }));
    expect(
      await screen.findByRole("heading", { name: "Sign in to Kanban Studio" })
    ).toBeInTheDocument();
    expect(authMocks.logout).toHaveBeenCalledOnce();
  });

  it("creates an account without email and signs the user in", async () => {
    const user = userEvent.setup();
    render(<AuthGate />);
    await screen.findByRole("heading", { name: "Sign in to Kanban Studio" });
    expect(
      screen.getByText(/Forgot your password\? Create a new account/)
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Create account" }));

    await user.type(screen.getByLabelText("Username"), "testuser");
    await user.type(screen.getByLabelText("Password"), "CorrectHorse123!");
    await user.type(screen.getByLabelText("Confirm password"), "CorrectHorse123!");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByRole("heading", { name: "Kanban Studio" }))
      .toBeInTheDocument();
    expect(authMocks.registerAccount).toHaveBeenCalledWith({
      username: "testuser",
      password: "CorrectHorse123!",
    });
    expect(authMocks.login).toHaveBeenCalledWith(
      "testuser",
      "CorrectHorse123!"
    );
  });
});
