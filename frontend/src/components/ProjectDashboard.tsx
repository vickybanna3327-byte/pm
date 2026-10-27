"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import { KanbanBoard } from "@/components/KanbanBoard";
import type { AuthUser } from "@/lib/authApi";
import {
  createProject,
  createTeamWorkspace,
  fetchDashboard,
  fetchProjects,
  fetchWorkspaces,
  type DashboardData,
  type Project,
  type Workspace,
} from "@/lib/projectApi";

const statusLabels = {
  backlog: "Backlog",
  todo: "To do",
  in_progress: "In progress",
  in_review: "In review",
  completed: "Completed",
} as const;

const metricCards = [
  ["total_projects", "Total projects", "text-[var(--primary-blue)]"],
  ["active_projects", "Active projects", "text-[var(--secondary-purple)]"],
  ["completed_projects", "Completed projects", "text-emerald-700"],
  ["total_assigned_tasks", "Assigned tasks", "text-[var(--navy-dark)]"],
  ["tasks_in_progress", "In progress", "text-[var(--primary-blue)]"],
  ["completed_tasks", "Completed tasks", "text-emerald-700"],
  ["overdue_tasks", "Overdue tasks", "text-red-700"],
  ["upcoming_deadlines", "Due in 7 days", "text-amber-700"],
] as const;

const panelClass =
  "rounded-2xl border border-[var(--stroke)] bg-white p-5 shadow-sm";

export const ProjectDashboard = ({
  currentUser,
  onLogout,
}: {
  currentUser: AuthUser;
  onLogout: () => void | Promise<void>;
}) => {
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [search, setSearch] = useState("");
  const [selectedWorkspace, setSelectedWorkspace] = useState("");
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [showProjectForm, setShowProjectForm] = useState(false);
  const [showWorkspaceForm, setShowWorkspaceForm] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const refreshDashboard = async () => {
    const result = await fetchDashboard();
    setDashboard(result);
  };

  useEffect(() => {
    let active = true;
    Promise.all([fetchDashboard(), fetchWorkspaces()])
      .then(([summary, workspaceRows]) => {
        if (!active) return;
        setDashboard(summary);
        setWorkspaces(workspaceRows);
        setLoading(false);
      })
      .catch((loadError: unknown) => {
        if (!active) return;
        setError(
          loadError instanceof Error
            ? loadError.message
            : "Unable to load your dashboard."
        );
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    fetchProjects(search)
      .then((projectRows) => {
        if (active) setProjects(projectRows);
      })
      .catch((loadError: unknown) => {
        if (active) {
          setError(
            loadError instanceof Error
              ? loadError.message
              : "Unable to load projects."
          );
        }
      });
    return () => {
      active = false;
    };
  }, [search]);

  const manageableWorkspaces = useMemo(
    () => workspaces.filter((workspace) => ["owner", "admin"].includes(workspace.role)),
    [workspaces]
  );

  const createProjectFromForm = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    setNotice("");
    const form = new FormData(event.currentTarget);
    try {
      await createProject(selectedWorkspace, {
        name: String(form.get("name")),
        description: String(form.get("description")),
        start_date: String(form.get("start_date") || "") || null,
        due_date: String(form.get("due_date") || "") || null,
        priority: String(form.get("priority")) as "low" | "medium" | "high",
        status: String(form.get("status")) as
          | "planning"
          | "active"
          | "on_hold"
          | "completed",
      });
      setShowProjectForm(false);
      setNotice("Project created.");
      await Promise.all([refreshDashboard(), fetchProjects(search).then(setProjects)]);
    } catch (createError) {
      setError(
        createError instanceof Error
          ? createError.message
          : "Unable to create the project."
      );
    } finally {
      setSaving(false);
    }
  };

  const createWorkspaceFromForm = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      const workspace = await createTeamWorkspace(
        String(form.get("name")),
        String(form.get("description"))
      );
      setWorkspaces((current) => [...current, workspace]);
      setSelectedWorkspace("");
      setShowWorkspaceForm(false);
      setNotice("Private team workspace created. Invite management is not available yet.");
    } catch (createError) {
      setError(
        createError instanceof Error
          ? createError.message
          : "Unable to create the workspace."
      );
    } finally {
      setSaving(false);
    }
  };

  if (selectedProject) {
    return (
      <KanbanBoard
        currentUser={currentUser}
        onLogout={onLogout}
        projectId={selectedProject.id}
        projectName={selectedProject.name}
        onBack={() => setSelectedProject(null)}
      />
    );
  }

  if (loading) {
    return (
      <main
        aria-label="Loading dashboard"
        aria-busy="true"
        className="flex min-h-screen items-center justify-center text-sm text-[var(--gray-text)]"
      >
        Loading your dashboard...
      </main>
    );
  }

  const metrics = dashboard?.metrics;

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-8 text-[var(--navy-dark)] sm:px-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <header className="flex flex-wrap items-center justify-between gap-4 rounded-3xl border border-[var(--stroke)] bg-white p-6 shadow-sm">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--gray-text)]">
              Kanban Studio
            </p>
            <h1 className="mt-2 font-display text-3xl font-semibold">
              Welcome, {dashboard?.user.name ?? currentUser.full_name ?? currentUser.username}
            </h1>
            <p className="mt-1 text-sm text-[var(--gray-text)]">
              {new Intl.DateTimeFormat(undefined, {
                weekday: "long",
                month: "long",
                day: "numeric",
                year: "numeric",
              }).format(new Date())}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <label className="sr-only" htmlFor="project-search">
              Search projects
            </label>
            <input
              id="project-search"
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search projects"
              className="min-h-11 rounded-full border border-[var(--stroke)] px-4 text-sm outline-none focus:border-[var(--primary-blue)]"
            />
            <button
              type="button"
              onClick={() => {
                setSelectedWorkspace(manageableWorkspaces[0]?.id ?? "");
                setShowProjectForm(true);
              }}
              disabled={!manageableWorkspaces.length}
              className="min-h-11 rounded-full bg-[var(--secondary-purple)] px-5 text-sm font-semibold text-white disabled:opacity-50"
            >
              Create project
            </button>
            <button
              type="button"
              onClick={() => setShowWorkspaceForm(true)}
              className="min-h-11 rounded-full border border-[var(--stroke)] px-4 text-sm font-semibold"
            >
              New team workspace
            </button>
            <div className="text-right">
              <p className="text-sm font-semibold">
                {currentUser.full_name || currentUser.username}
              </p>
              <button
                type="button"
                onClick={() => void onLogout()}
                className="text-sm text-[var(--primary-blue)] hover:underline"
              >
                Log out
              </button>
            </div>
          </div>
        </header>

        {error && (
          <p role="alert" className="rounded-xl bg-red-50 p-4 text-sm text-red-800">
            {error}
          </p>
        )}
        {notice && (
          <p role="status" className="rounded-xl bg-blue-50 p-4 text-sm text-blue-800">
            {notice}
          </p>
        )}

        <section aria-label="Project and task metrics" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {metricCards.map(([key, title, color]) => (
            <article key={key} className={panelClass}>
              <p className="text-sm text-[var(--gray-text)]">{title}</p>
              <p className={`mt-3 text-3xl font-semibold ${color}`}>
                {metrics?.[key] ?? 0}
              </p>
            </article>
          ))}
        </section>

        <section className="grid gap-6 xl:grid-cols-[1.3fr_1fr]">
          <div className={panelClass}>
            <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold">My projects</h2>
                <p className="mt-1 text-sm text-[var(--gray-text)]">
                  Projects in workspaces you can access.
                </p>
              </div>
              <label className="text-sm">
                <span className="sr-only">Filter projects by workspace</span>
                <select
                  aria-label="Filter projects by workspace"
                  value={selectedWorkspace}
                  onChange={(event) => setSelectedWorkspace(event.target.value)}
                  className="rounded-full border border-[var(--stroke)] bg-white px-3 py-2"
                >
                  <option value="">All workspaces</option>
                  {workspaces.map((workspace) => (
                    <option key={workspace.id} value={workspace.id}>
                      {workspace.name}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            {projects.filter(
              (project) =>
                !selectedWorkspace || project.workspace_id === selectedWorkspace
            ).length === 0 ? (
              <div className="rounded-2xl border border-dashed border-[var(--stroke)] p-8 text-center">
                <p className="font-semibold">No projects found</p>
                <p className="mt-2 text-sm text-[var(--gray-text)]">
                  Create a project to start organizing work.
                </p>
              </div>
            ) : (
              <div className="grid gap-3 md:grid-cols-2">
                {projects
                  .filter(
                    (project) =>
                      !selectedWorkspace ||
                      project.workspace_id === selectedWorkspace
                  )
                  .map((project) => (
                    <article
                      key={project.id}
                      className="rounded-2xl border border-[var(--stroke)] p-4"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <h3 className="truncate font-semibold">{project.name}</h3>
                          <p className="mt-1 line-clamp-2 min-h-10 text-sm text-[var(--gray-text)]">
                            {project.description || "No description"}
                          </p>
                        </div>
                        <span
                          className="mt-1 h-3 w-3 shrink-0 rounded-full"
                          style={{ backgroundColor: project.color }}
                          aria-label={`Project color ${project.color}`}
                        />
                      </div>
                      <div className="mt-3 flex items-center justify-between text-xs text-[var(--gray-text)]">
                        <span className="capitalize">{project.status.replace("_", " ")}</span>
                        <span className="capitalize">{project.priority} priority</span>
                      </div>
                      {project.due_date && (
                        <p className="mt-2 text-xs text-[var(--gray-text)]">
                          Due {project.due_date}
                        </p>
                      )}
                      <button
                        type="button"
                        disabled={!project.board_id}
                        onClick={() => setSelectedProject(project)}
                        className="mt-4 min-h-10 w-full rounded-full border border-[var(--stroke)] text-sm font-semibold hover:border-[var(--primary-blue)] hover:text-[var(--primary-blue)] disabled:opacity-50"
                      >
                        Open board
                      </button>
                    </article>
                  ))}
              </div>
            )}
          </div>

          <section className={panelClass} aria-label="Task status distribution">
            <h2 className="text-lg font-semibold">Task status</h2>
            <p className="mb-5 mt-1 text-sm text-[var(--gray-text)]">
              Tasks across your accessible projects.
            </p>
            <div className="space-y-4">
              {Object.entries(statusLabels).map(([key, label]) => {
                const count = dashboard?.task_status_distribution[key as keyof typeof statusLabels] ?? 0;
                const total = Object.values(
                  dashboard?.task_status_distribution ?? {}
                ).reduce((sum, value) => sum + value, 0);
                const percent = total ? (count / total) * 100 : 0;
                return (
                  <div key={key}>
                    <div className="mb-1 flex justify-between text-sm">
                      <span>{label}</span>
                      <span className="font-semibold">{count}</span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                      <div
                        className="h-full rounded-full bg-[var(--primary-blue)]"
                        style={{ width: `${percent}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        </section>

        <section className="grid gap-6 lg:grid-cols-2">
          <section className={panelClass} aria-label="Project progress">
            <h2 className="text-lg font-semibold">Project progress</h2>
            <div className="mt-4 space-y-4">
              {(dashboard?.project_progress ?? []).map((project) => (
                <div key={project.project_id}>
                  <div className="mb-1 flex justify-between gap-3 text-sm">
                    <span className="truncate">{project.project_name}</span>
                    <span>{project.progress_percent}%</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                    <div
                      className="h-full rounded-full bg-[var(--accent-yellow)]"
                      style={{ width: `${project.progress_percent}%` }}
                    />
                  </div>
                  <p className="mt-1 text-xs text-[var(--gray-text)]">
                    {project.completed_tasks} of {project.total_tasks} tasks complete
                  </p>
                </div>
              ))}
              {!dashboard?.project_progress.length && (
                <p className="text-sm text-[var(--gray-text)]">
                  Project progress will appear when boards have tasks.
                </p>
              )}
            </div>
          </section>

          <section className={panelClass} aria-label="Upcoming deadlines">
            <h2 className="text-lg font-semibold">Upcoming deadlines</h2>
            <div className="mt-4 divide-y divide-[var(--stroke)]">
              {(dashboard?.upcoming_deadline_items ?? []).map((task) => (
                <div key={task.id} className="flex items-center justify-between gap-3 py-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold">{task.title}</p>
                    <p className="text-xs text-[var(--gray-text)]">{task.project_name}</p>
                  </div>
                  <div className="shrink-0 text-right">
                    <p className="text-sm">{task.due_date}</p>
                    <p className="text-xs capitalize text-[var(--gray-text)]">
                      {task.priority} priority
                    </p>
                  </div>
                </div>
              ))}
              {!dashboard?.upcoming_deadline_items.length && (
                <p className="py-3 text-sm text-[var(--gray-text)]">
                  No task deadlines in the next seven days.
                </p>
              )}
            </div>
          </section>

          <section className={panelClass} aria-label="Completed tasks over time">
            <h2 className="text-lg font-semibold">Completed over time</h2>
            <div className="mt-5 flex h-36 items-end gap-2">
              {(dashboard?.completed_over_time ?? []).slice(-14).map((day) => {
                const maximum = Math.max(
                  ...(dashboard?.completed_over_time.map((item) => item.count) ?? [1]),
                  1
                );
                return (
                  <div
                    key={day.date}
                    className="flex h-full flex-1 flex-col items-center justify-end gap-1"
                    title={`${day.date}: ${day.count} completed`}
                  >
                    <div
                      className="w-full rounded-t bg-[var(--secondary-purple)]"
                      style={{ height: `${Math.max((day.count / maximum) * 100, 4)}%` }}
                    />
                    <span className="text-[10px] text-[var(--gray-text)]">
                      {day.date.slice(5)}
                    </span>
                  </div>
                );
              })}
              {!dashboard?.completed_over_time.length && (
                <p className="self-center text-sm text-[var(--gray-text)]">
                  Completion history will appear as tasks are completed.
                </p>
              )}
            </div>
          </section>

          <section className={panelClass} aria-label="Workload by team member">
            <h2 className="text-lg font-semibold">Workload by team member</h2>
            <div className="mt-4 space-y-3">
              {(dashboard?.workload_by_member ?? []).map((member) => (
                <div key={member.user_id} className="flex items-center gap-3">
                  <span className="w-28 truncate text-sm">{member.name}</span>
                  <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
                    <div
                      className="h-full rounded-full bg-[var(--primary-blue)]"
                      style={{
                        width: `${
                          member.total_tasks
                            ? (member.completed_tasks / member.total_tasks) * 100
                            : 0
                        }%`,
                      }}
                    />
                  </div>
                  <span className="text-xs text-[var(--gray-text)]">
                    {member.completed_tasks}/{member.total_tasks}
                  </span>
                </div>
              ))}
              {!dashboard?.workload_by_member.length && (
                <p className="text-sm text-[var(--gray-text)]">
                  Workload will appear after tasks are assigned.
                </p>
              )}
            </div>
          </section>
        </section>

        <section className={panelClass} aria-label="High-priority tasks">
          <h2 className="text-lg font-semibold">High-priority tasks</h2>
          <div className="mt-3 grid gap-2 md:grid-cols-2 lg:grid-cols-3">
            {(dashboard?.high_priority_tasks ?? []).map((task) => (
              <div key={task.id} className="rounded-xl bg-amber-50 p-3">
                <p className="font-semibold">{task.title}</p>
                <p className="mt-1 text-xs text-[var(--gray-text)]">
                  {task.project_name} · {task.due_date || "No due date"}
                </p>
              </div>
            ))}
            {!dashboard?.high_priority_tasks.length && (
              <p className="text-sm text-[var(--gray-text)]">
                No open high-priority tasks.
              </p>
            )}
          </div>
        </section>
      </div>

      {showProjectForm && (
        <div
          className="fixed inset-0 z-30 flex items-center justify-center bg-slate-950/40 p-4"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setShowProjectForm(false);
          }}
        >
          <form
            aria-label="Create project"
            onSubmit={(event) => void createProjectFromForm(event)}
            className="max-h-[90vh] w-full max-w-lg space-y-4 overflow-y-auto rounded-3xl bg-white p-6 shadow-2xl"
          >
            <div>
              <h2 className="text-xl font-semibold">Create project</h2>
              <p className="mt-1 text-sm text-[var(--gray-text)]">
                A project gets its own private Kanban board.
              </p>
            </div>
            <label className="block text-sm font-medium">
              Workspace
              <select
                required
                value={selectedWorkspace}
                onChange={(event) => setSelectedWorkspace(event.target.value)}
                className="mt-1 min-h-11 w-full rounded-xl border border-[var(--stroke)] px-3"
              >
                {manageableWorkspaces.map((workspace) => (
                  <option key={workspace.id} value={workspace.id}>
                    {workspace.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm font-medium">
              Project name
              <input
                name="name"
                required
                maxLength={120}
                className="mt-1 min-h-11 w-full rounded-xl border border-[var(--stroke)] px-3"
              />
            </label>
            <label className="block text-sm font-medium">
              Description
              <textarea
                name="description"
                maxLength={4000}
                rows={3}
                className="mt-1 w-full rounded-xl border border-[var(--stroke)] px-3 py-2"
              />
            </label>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block text-sm font-medium">
                Start date
                <input
                  type="date"
                  name="start_date"
                  className="mt-1 min-h-11 w-full rounded-xl border border-[var(--stroke)] px-3"
                />
              </label>
              <label className="block text-sm font-medium">
                Due date
                <input
                  type="date"
                  name="due_date"
                  className="mt-1 min-h-11 w-full rounded-xl border border-[var(--stroke)] px-3"
                />
              </label>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block text-sm font-medium">
                Priority
                <select
                  name="priority"
                  defaultValue="medium"
                  className="mt-1 min-h-11 w-full rounded-xl border border-[var(--stroke)] px-3"
                >
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                </select>
              </label>
              <label className="block text-sm font-medium">
                Status
                <select
                  name="status"
                  defaultValue="planning"
                  className="mt-1 min-h-11 w-full rounded-xl border border-[var(--stroke)] px-3"
                >
                  <option value="planning">Planning</option>
                  <option value="active">Active</option>
                  <option value="on_hold">On hold</option>
                  <option value="completed">Completed</option>
                </select>
              </label>
            </div>
            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setShowProjectForm(false)}
                className="min-h-11 rounded-full border border-[var(--stroke)] px-5 text-sm font-semibold"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={saving || !manageableWorkspaces.length}
                className="min-h-11 rounded-full bg-[var(--secondary-purple)] px-5 text-sm font-semibold text-white disabled:opacity-50"
              >
                {saving ? "Creating..." : "Create project"}
              </button>
            </div>
          </form>
        </div>
      )}

      {showWorkspaceForm && (
        <div className="fixed inset-0 z-30 flex items-center justify-center bg-slate-950/40 p-4">
          <form
            aria-label="Create team workspace"
            onSubmit={(event) => void createWorkspaceFromForm(event)}
            className="w-full max-w-md space-y-4 rounded-3xl bg-white p-6 shadow-2xl"
          >
            <h2 className="text-xl font-semibold">Create team workspace</h2>
            <p className="text-sm text-[var(--gray-text)]">
              Team workspaces are private. Invite management will be added separately.
            </p>
            <label className="block text-sm font-medium">
              Workspace name
              <input
                name="name"
                required
                maxLength={80}
                className="mt-1 min-h-11 w-full rounded-xl border border-[var(--stroke)] px-3"
              />
            </label>
            <label className="block text-sm font-medium">
              Description
              <textarea
                name="description"
                maxLength={1000}
                rows={3}
                className="mt-1 w-full rounded-xl border border-[var(--stroke)] px-3 py-2"
              />
            </label>
            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setShowWorkspaceForm(false)}
                className="min-h-11 rounded-full border border-[var(--stroke)] px-5 text-sm font-semibold"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={saving}
                className="min-h-11 rounded-full bg-[var(--secondary-purple)] px-5 text-sm font-semibold text-white"
              >
                {saving ? "Creating..." : "Create workspace"}
              </button>
            </div>
          </form>
        </div>
      )}
    </main>
  );
};
