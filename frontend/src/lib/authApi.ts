export type AuthUser = {
  id: string;
  username: string;
  email: string | null;
  full_name: string;
  role: string;
};

export class AuthApiError extends Error {
  constructor(
    message: string,
    readonly status: number
  ) {
    super(message);
  }
}

const request = async <T>(
  path: string,
  body?: Record<string, string>
): Promise<T> => {
  const response = await fetch(`/api/auth/${path}`, {
    method: body ? "POST" : "GET",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
    credentials: "same-origin",
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const payload: unknown = await response.json();
      if (payload && typeof payload === "object" && "detail" in payload) {
        detail = String(payload.detail);
      }
    } catch {
      // Keep the HTTP status text if the response isn't JSON.
    }
    throw new AuthApiError(
      detail || `Request failed (${response.status}).`,
      response.status
    );
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
};

export const getCurrentUser = async (): Promise<AuthUser> => {
  const result = await request<{ user: AuthUser }>("me");
  return result.user;
};

export const registerAccount = (input: {
  username: string;
  password: string;
}) => request<{ message: string }>("register", input);

export const login = (identifier: string, password: string) =>
  request<{ user: AuthUser }>("login", { identifier, password });

export const logout = () => request<void>("logout", {});

export const changePassword = (
  current_password: string,
  new_password: string
) =>
  request<{ message: string }>("change-password", {
    current_password,
    new_password,
  });
