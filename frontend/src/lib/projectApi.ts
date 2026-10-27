export type Workspace = {
  id: string;
  name: string;
  description: string;
  kind: "personal" | "team";
  owner_id: string;
  role: "owner" | "admin" | "member" | "viewer";
  project_count: number;
};

export type Project = {
  id: string;
  workspace_id: string;
  owner_id: string;
  name: string;
  description: string;
  start_date: string | null;
  due_date: string | null;
  priority: "low" | "medium" | "high";
  status: "planning" | "active" | "on_hold" | "completed" | "archived";
  color: string;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
  board_id: string | null;
  member_count: number;
};

export type DashboardData = {
  user: { id: string; name: string; username: string };
  metrics: {
    total_projects: number;
    active_projects: number;
    completed_projects: number;
    total_assigned_tasks: number;
    tasks_in_progress: number;
    completed_tasks: number;
    overdue_tasks: number;
    upcoming_deadlines: number;
  };
  task_status_distribution: Record<
    "backlog" | "todo" | "in_progress" | "in_review" | "completed",
    number
  >;
  completed_over_time: Array<{ date: string; count: number }>;
  project_progress: Array<{
    project_id: string;
    project_name: string;
    status: string;
    total_tasks: number;
    completed_tasks: number;
    progress_percent: number;
  }>;
  upcoming_deadline_items: Array<{
    id: string;
    title: string;
    project_id: string;
    project_name: string;
    due_date: string;
    priority: "low" | "medium" | "high";
  }>;
  workload_by_member: Array<{
    user_id: string;
    username: string;
    name: string;
    total_tasks: number;
    completed_tasks: number;
  }>;
  high_priority_tasks: Array<{
    id: string;
    title: string;
    project_id: string;
    project_name: string;
    status: string;
    due_date: string | null;
  }>;
};

const requestJson = async <T>(path: string, init?: RequestInit): Promise<T> => {
  const response = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body: unknown = await response.json();
      if (body && typeof body === "object" && "detail" in body) {
        detail = String(body.detail);
      }
    } catch {
      // Keep the HTTP status text if the response isn't JSON.
    }
    throw new Error(detail || `Request failed (${response.status}).`);
  }
  return (await response.json()) as T;
};

export const fetchDashboard = () =>
  requestJson<DashboardData>("/api/dashboard");

export const fetchProjects = (search = "") =>
  requestJson<Project[]>(
    `/api/projects${search ? `?search=${encodeURIComponent(search)}` : ""}`
  );

export const fetchWorkspaces = () =>
  requestJson<Workspace[]>("/api/workspaces");

export const createProject = (
  workspaceId: string,
  project: {
    name: string;
    description: string;
    start_date: string | null;
    due_date: string | null;
    priority: "low" | "medium" | "high";
    status: "planning" | "active" | "on_hold" | "completed";
  }
) =>
  requestJson<Project>(`/api/workspaces/${encodeURIComponent(workspaceId)}/projects`, {
    method: "POST",
    body: JSON.stringify(project),
  });

export const createTeamWorkspace = (name: string, description = "") =>
  requestJson<Workspace>("/api/workspaces", {
    method: "POST",
    body: JSON.stringify({ name, description }),
  });
