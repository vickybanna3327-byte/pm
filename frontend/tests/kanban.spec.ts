import { expect, test, type Page } from "@playwright/test";
import { initialData, type BoardData } from "../src/lib/kanban";

const installBoardApiMock = async (page: Page) => {
  const board: BoardData = structuredClone(initialData);
  let nextCardId = 0;
  let signedIn = false;
  const projectId = "project-user";
  const project = {
    id: projectId,
    workspace_id: "personal-user",
    owner_id: "user",
    name: "Kanban Studio",
    description: "Test project",
    start_date: null,
    due_date: null,
    priority: "medium",
    status: "active",
    color: "#209dd7",
    created_at: "2026-10-01T00:00:00Z",
    updated_at: "2026-10-01T00:00:00Z",
    archived_at: null,
    board_id: "board-user",
    member_count: 1,
  };
  await page.route("**/api/dashboard", async (route) => {
    await route.fulfill({
      json: {
        user: { id: "user", name: "Test User", username: "user" },
        metrics: {
          total_projects: 1,
          active_projects: 1,
          completed_projects: 0,
          total_assigned_tasks: 0,
          tasks_in_progress: 0,
          completed_tasks: 0,
          overdue_tasks: 0,
          upcoming_deadlines: 0,
        },
        task_status_distribution: {
          backlog: 2,
          todo: 1,
          in_progress: 2,
          in_review: 1,
          completed: 2,
        },
        completed_over_time: [],
        project_progress: [],
        upcoming_deadline_items: [],
        workload_by_member: [],
        high_priority_tasks: [],
      },
    });
  });
  await page.route("**/api/workspaces", async (route) => {
    await route.fulfill({
      json: [
        {
          id: "personal-user",
          name: "Test User's Workspace",
          description: "",
          kind: "personal",
          owner_id: "user",
          role: "owner",
          project_count: 1,
        },
      ],
    });
  });
  await page.route("**/api/projects", async (route) => {
    await route.fulfill({ json: [project] });
  });

  await page.route("**/api/auth/**", async (route) => {
    const { pathname } = new URL(route.request().url());
    const method = route.request().method();
    if (pathname === "/api/auth/me" && method === "GET") {
      await route.fulfill(
        signedIn
          ? {
              json: {
                user: {
                  id: "user",
                  username: "user",
                  email: "user@example.com",
                  full_name: "Test User",
                  role: "member",
                },
              },
            }
          : { status: 401, json: { detail: "Authentication required." } }
      );
      return;
    }
    if (pathname === "/api/auth/login" && method === "POST") {
      if (route.request().postDataJSON().password !== "password") {
        await route.fulfill({
          status: 401,
          json: { detail: "Invalid username/email or password." },
        });
        return;
      }
      signedIn = true;
      await route.fulfill({
        json: {
          user: {
            id: "user",
            username: "user",
            email: "user@example.com",
            full_name: "Test User",
            role: "member",
          },
        },
      });
      return;
    }
    if (pathname === "/api/auth/logout" && method === "POST") {
      signedIn = false;
      await route.fulfill({ status: 204 });
      return;
    }
    if (pathname === "/api/auth/register" && method === "POST") {
      await route.fulfill({ status: 202, json: { message: "Code sent." } });
      return;
    }
    if (pathname === "/api/auth/verify-email" && method === "POST") {
      await route.fulfill({ json: { message: "Email verified." } });
      return;
    }
    if (pathname === "/api/auth/forgot-password" && method === "POST") {
      await route.fulfill({ status: 202, json: { message: "Reset code sent." } });
      return;
    }
    if (pathname === "/api/auth/verify-reset-code" && method === "POST") {
      await route.fulfill({ json: { reset_token: "mock-reset-token" } });
      return;
    }
    if (pathname === "/api/auth/reset-password" && method === "POST") {
      await route.fulfill({ json: { message: "Password reset." } });
      return;
    }
    await route.fulfill({ status: 404, json: { detail: "Not found." } });
  });

  await page.route("**/api/**/board**", async (route) => {
    const { pathname } = new URL(route.request().url());
    const method = route.request().method();
    const projectBoard = pathname.match(
      /^\/api\/projects\/([^/]+)\/board(?:\/.*)?$/
    );
    const basePath = projectBoard
      ? `/api/projects/${projectBoard[1]}/board`
      : "/api/users/me/board";
    const relativePath = pathname.slice(basePath.length);

    if (relativePath === "" && method === "GET") {
      await route.fulfill({ json: board });
      return;
    }

    if (relativePath === "/chat" && method === "POST") {
      const { question, history } = route.request().postDataJSON();
      let reply = history.length
        ? "I remember our earlier exchange."
        : "The board has eight cards.";
      let changed = false;

      if (question === "Move the roadmap card to Review.") {
        const source = board.columns.find((column) =>
          column.cardIds.includes("card-1")
        );
        const target = board.columns.find(
          (column) => column.id === "col-review"
        );
        if (source && target) {
          source.cardIds = source.cardIds.filter((id) => id !== "card-1");
          target.cardIds.unshift("card-1");
          changed = true;
        }
        reply = history.length
          ? "Moved the roadmap card using our earlier context."
          : "Moved the roadmap card to Review.";
      }

      await route.fulfill({
        json: {
          model: "openai/gpt-oss-120b",
          reply,
          board,
          changed,
        },
      });
      return;
    }

    const columnMatch = relativePath.match(/^\/columns\/([^/]+)$/);
    if (columnMatch && method === "PATCH") {
      const column = board.columns.find(
        (item) => item.id === decodeURIComponent(columnMatch[1])
      );
      if (column) {
        column.title = String(route.request().postDataJSON().title);
      }
      await route.fulfill({ json: board });
      return;
    }

    const createMatch = relativePath.match(/^\/columns\/([^/]+)\/cards$/);
    if (createMatch && method === "POST") {
      const column = board.columns.find(
        (item) => item.id === decodeURIComponent(createMatch[1])
      );
      if (column) {
        const card = {
          id: `e2e-card-${++nextCardId}`,
          ...route.request().postDataJSON(),
        };
        board.cards[card.id] = card;
        column.cardIds.push(card.id);
      }
      await route.fulfill({ status: 201, json: board });
      return;
    }

    const deleteMatch = relativePath.match(/^\/cards\/([^/]+)$/);
    if (deleteMatch && method === "DELETE") {
      const cardId = decodeURIComponent(deleteMatch[1]);
      delete board.cards[cardId];
      board.columns.forEach((column) => {
        column.cardIds = column.cardIds.filter((id) => id !== cardId);
      });
      await route.fulfill({ json: board });
      return;
    }

    const updateMatch = relativePath.match(/^\/cards\/([^/]+)$/);
    if (updateMatch && method === "PATCH") {
      const cardId = decodeURIComponent(updateMatch[1]);
      if (board.cards[cardId]) {
        Object.assign(board.cards[cardId], route.request().postDataJSON());
      }
      await route.fulfill({ json: board });
      return;
    }

    const moveMatch = relativePath.match(/^\/cards\/([^/]+)\/move$/);
    if (moveMatch && method === "POST") {
      const cardId = decodeURIComponent(moveMatch[1]);
      const { column_id: targetId, position } = route.request().postDataJSON();
      const source = board.columns.find((column) =>
        column.cardIds.includes(cardId)
      );
      const target = board.columns.find((column) => column.id === targetId);
      if (source && target) {
        source.cardIds = source.cardIds.filter((id) => id !== cardId);
        const insertAt =
          typeof position === "number" ? position : target.cardIds.length;
        target.cardIds.splice(insertAt, 0, cardId);
      }
      await route.fulfill({ json: board });
      return;
    }

    await route.fulfill({ status: 404, json: { detail: "Not found." } });
  });
};

test.beforeEach(async ({ page }) => {
  await installBoardApiMock(page);
});

const signInAndOpenBoard = async (page: Page) => {
  await page.goto("/");
  await page.getByLabel("Username").fill("user");
  await page.getByRole("textbox", { name: "Password" }).fill("password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByRole("button", { name: "Open board" }).click();
};

test("loads the kanban board", async ({ page }) => {
  await signInAndOpenBoard(page);
  await expect(page.getByRole("heading", { name: "Kanban Studio" })).toBeVisible();
  await expect(page.locator('[data-testid^="column-"]')).toHaveCount(5);
});

test("adds a card to a column", async ({ page }) => {
  await signInAndOpenBoard(page);
  const firstColumn = page.locator('[data-testid^="column-"]').first();
  await firstColumn.getByRole("button", { name: /add a card/i }).click();
  await firstColumn.getByPlaceholder("Card title").fill("Playwright card");
  await firstColumn.getByPlaceholder("Details").fill("Added via e2e.");
  await firstColumn.getByRole("button", { name: /add card/i }).click();
  await expect(firstColumn.getByText("Playwright card")).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: "Open board" }).click();
  await expect(
    page.locator('[data-testid^="column-"]').first().getByText("Playwright card")
  ).toBeVisible();
});

test("moves a card between columns", async ({ page }) => {
  await signInAndOpenBoard(page);
  const card = page.getByTestId("card-card-1");
  const targetColumn = page.getByTestId("column-col-review");
  const cardBox = await card.boundingBox();
  const columnBox = await targetColumn.boundingBox();
  if (!cardBox || !columnBox) {
    throw new Error("Unable to resolve drag coordinates.");
  }

  await page.mouse.move(
    cardBox.x + cardBox.width / 2,
    cardBox.y + cardBox.height / 2
  );
  await page.mouse.down();
  await page.mouse.move(
    columnBox.x + columnBox.width / 2,
    columnBox.y + 120,
    { steps: 12 }
  );
  await page.mouse.up();
  await expect(targetColumn.getByTestId("card-card-1")).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: "Open board" }).click();
  await expect(
    page.getByTestId("column-col-review").getByTestId("card-card-1")
  ).toBeVisible();
});

test("persists column renames and card deletion", async ({ page }) => {
  await signInAndOpenBoard(page);

  const columnTitle = page.getByLabel("Column title").first();
  await columnTitle.fill("Ready");
  await columnTitle.press("Tab");
  await expect(columnTitle).toHaveValue("Ready");

  const card = page.getByTestId("card-card-1");
  await card.getByRole("button", { name: "Delete Align roadmap themes" }).click();
  await expect(card).not.toBeVisible();

  await page.reload();
  await page.getByRole("button", { name: "Open board" }).click();
  await expect(page.getByLabel("Column title").first()).toHaveValue("Ready");
  await expect(page.getByTestId("card-card-1")).not.toBeVisible();
});

test("edits and persists a card's title and details", async ({ page }) => {
  await signInAndOpenBoard(page);

  const card = page.getByTestId("card-card-1");
  await card.getByRole("button", { name: "Edit Align roadmap themes" }).click();
  await card.getByRole("textbox", {
    name: "Edit title for Align roadmap themes",
  }).fill("Updated roadmap");
  await card.getByRole("textbox", {
    name: "Edit details for Align roadmap themes",
  }).fill("Updated impact statements.");
  await card.getByRole("button", { name: "Save changes" }).click();

  await expect(card.getByRole("heading", { name: "Updated roadmap" })).toBeVisible();
  await expect(card.getByText("Updated impact statements.")).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: "Open board" }).click();
  const persistedCard = page.getByTestId("card-card-1");
  await expect(
    persistedCard.getByRole("heading", { name: "Updated roadmap" })
  ).toBeVisible();
  await expect(persistedCard.getByText("Updated impact statements.")).toBeVisible();
});

test("chat keeps conversation context and refreshes AI board changes", async ({
  page,
}) => {
  await signInAndOpenBoard(page);

  const chat = page.getByRole("complementary", {
    name: "AI board assistant",
  });
  const message = chat.getByLabel("Message the board assistant");
  await message.fill("How many cards are on the board?");
  await chat.getByRole("button", { name: "Send" }).click();
  await expect(chat.getByText("The board has eight cards.")).toBeVisible();

  await message.fill("Move the roadmap card to Review.");
  await chat.getByRole("button", { name: "Send" }).click();
  await expect(
    chat.getByText("Moved the roadmap card using our earlier context.")
  ).toBeVisible();
  await expect(
    page.getByTestId("column-col-review").getByTestId("card-card-1")
  ).toBeVisible();
  await expect(
    chat.getByText("How many cards are on the board?")
  ).toBeVisible();
});

test("keeps card actions inside each card at desktop widths", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await signInAndOpenBoard(page);

  const card = page.getByTestId("card-card-1");
  const edit = card.getByRole("button", { name: "Edit Align roadmap themes" });
  const remove = card.getByRole("button", {
    name: "Delete Align roadmap themes",
  });
  await expect(edit).toBeVisible();
  await expect(remove).toBeVisible();

  const cardBounds = await card.boundingBox();
  const editBounds = await edit.boundingBox();
  const removeBounds = await remove.boundingBox();
  if (!cardBounds || !editBounds || !removeBounds) {
    throw new Error("Unable to resolve card action coordinates.");
  }

  expect(editBounds.x).toBeGreaterThanOrEqual(cardBounds.x);
  expect(editBounds.x + editBounds.width).toBeLessThanOrEqual(
    cardBounds.x + cardBounds.width
  );
  expect(removeBounds.x).toBeGreaterThanOrEqual(cardBounds.x);
  expect(removeBounds.x + removeBounds.width).toBeLessThanOrEqual(
    cardBounds.x + cardBounds.width
  );
});

test("keeps the board aligned without page-level horizontal overflow", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1366, height: 900 });
  await signInAndOpenBoard(page);

  const boardGrid = page.getByTestId("column-col-backlog");
  const mediumTracks = await boardGrid.evaluate(
    (column) => getComputedStyle(column.parentElement!).gridTemplateColumns
  );
  expect(mediumTracks.trim().split(/\s+/)).toHaveLength(3);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth
    )
  ).toBe(true);

  await page.setViewportSize({ width: 1600, height: 900 });
  const wideTracks = await boardGrid.evaluate(
    (column) => getComputedStyle(column.parentElement!).gridTemplateColumns
  );
  expect(wideTracks.trim().split(/\s+/)).toHaveLength(5);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth
    )
  ).toBe(true);
});

test("rejects invalid credentials and supports logout", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Username").fill("user");
  await page.getByRole("textbox", { name: "Password" }).fill("incorrect");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(
    page.getByText("Invalid username/email or password.")
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Welcome, Test User" })
  ).not.toBeVisible();

  await page.getByRole("textbox", { name: "Password" }).fill("password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(
    page.getByRole("heading", { name: "Welcome, Test User" })
  ).toBeVisible();
  await page.getByRole("button", { name: "Open board" }).click();

  const card = page.getByTestId("card-card-1");
  const targetColumn = page.getByTestId("column-col-review");
  const cardBox = await card.boundingBox();
  const columnBox = await targetColumn.boundingBox();
  if (!cardBox || !columnBox) {
    throw new Error("Unable to resolve drag coordinates.");
  }
  await page.mouse.move(
    cardBox.x + cardBox.width / 2,
    cardBox.y + cardBox.height / 2
  );
  await page.mouse.down();
  await page.mouse.move(
    columnBox.x + columnBox.width / 2,
    columnBox.y + 120,
    { steps: 12 }
  );
  await page.mouse.up();
  await expect(targetColumn.getByTestId("card-card-1")).toBeVisible();

  await page.getByRole("button", { name: "Test User" }).click();
  await page.getByRole("button", { name: "Log out" }).click();
  await page.getByLabel("Username").fill("user");
  await page.getByRole("textbox", { name: "Password" }).fill("password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByRole("button", { name: "Open board" }).click();
  await expect(
    page.getByTestId("column-col-review").getByTestId("card-card-1")
  ).toBeVisible();

  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Welcome, Test User" })
  ).toBeVisible();
  await page.getByRole("button", { name: "Open board" }).click();
  await page.getByRole("button", { name: "Test User" }).click();
  await page.getByRole("button", { name: "Log out" }).click();
  await expect(
    page.getByRole("heading", { name: "Sign in to Kanban Studio" })
  ).toBeVisible();
});
