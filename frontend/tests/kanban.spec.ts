import { expect, test, type Page } from "@playwright/test";
import { initialData, type BoardData } from "../src/lib/kanban";

const installBoardApiMock = async (page: Page) => {
  const board: BoardData = structuredClone(initialData);
  let nextCardId = 0;

  await page.route("**/api/users/user/board**", async (route) => {
    const { pathname } = new URL(route.request().url());
    const method = route.request().method();
    const basePath = "/api/users/user/board";

    if (pathname === basePath && method === "GET") {
      await route.fulfill({ json: board });
      return;
    }

    const columnMatch = pathname.match(
      /^\/api\/users\/user\/board\/columns\/([^/]+)$/
    );
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

    const createMatch = pathname.match(
      /^\/api\/users\/user\/board\/columns\/([^/]+)\/cards$/
    );
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

    const deleteMatch = pathname.match(
      /^\/api\/users\/user\/board\/cards\/([^/]+)$/
    );
    if (deleteMatch && method === "DELETE") {
      const cardId = decodeURIComponent(deleteMatch[1]);
      delete board.cards[cardId];
      board.columns.forEach((column) => {
        column.cardIds = column.cardIds.filter((id) => id !== cardId);
      });
      await route.fulfill({ json: board });
      return;
    }

    const moveMatch = pathname.match(
      /^\/api\/users\/user\/board\/cards\/([^/]+)\/move$/
    );
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

test("loads the kanban board", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Username").fill("user");
  await page.getByLabel("Password").fill("password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Kanban Studio" })).toBeVisible();
  await expect(page.locator('[data-testid^="column-"]')).toHaveCount(5);
});

test("adds a card to a column", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Username").fill("user");
  await page.getByLabel("Password").fill("password");
  await page.getByRole("button", { name: "Sign in" }).click();
  const firstColumn = page.locator('[data-testid^="column-"]').first();
  await firstColumn.getByRole("button", { name: /add a card/i }).click();
  await firstColumn.getByPlaceholder("Card title").fill("Playwright card");
  await firstColumn.getByPlaceholder("Details").fill("Added via e2e.");
  await firstColumn.getByRole("button", { name: /add card/i }).click();
  await expect(firstColumn.getByText("Playwright card")).toBeVisible();
  await page.reload();
  await expect(
    page.locator('[data-testid^="column-"]').first().getByText("Playwright card")
  ).toBeVisible();
});

test("moves a card between columns", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Username").fill("user");
  await page.getByLabel("Password").fill("password");
  await page.getByRole("button", { name: "Sign in" }).click();
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
  await expect(
    page.getByTestId("column-col-review").getByTestId("card-card-1")
  ).toBeVisible();
});

test("persists column renames and card deletion", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Username").fill("user");
  await page.getByLabel("Password").fill("password");
  await page.getByRole("button", { name: "Sign in" }).click();

  const columnTitle = page.getByLabel("Column title").first();
  await columnTitle.fill("Ready");
  await columnTitle.press("Tab");
  await expect(columnTitle).toHaveValue("Ready");

  const card = page.getByTestId("card-card-1");
  await card.getByRole("button", { name: "Delete Align roadmap themes" }).click();
  await expect(card).not.toBeVisible();

  await page.reload();
  await expect(page.getByLabel("Column title").first()).toHaveValue("Ready");
  await expect(page.getByTestId("card-card-1")).not.toBeVisible();
});

test("rejects invalid credentials and supports logout", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Username").fill("user");
  await page.getByLabel("Password").fill("incorrect");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText("Incorrect username or password.")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Kanban Studio", exact: true })
  ).not.toBeVisible();

  await page.getByLabel("Password").fill("password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(
    page.getByRole("heading", { name: "Kanban Studio" })
  ).toBeVisible();

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

  await page.getByRole("button", { name: "Log out" }).click();
  await page.getByLabel("Username").fill("user");
  await page.getByLabel("Password").fill("password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(
    page.getByTestId("column-col-review").getByTestId("card-card-1")
  ).toBeVisible();

  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Kanban Studio" })
  ).toBeVisible();
  await page.getByRole("button", { name: "Log out" }).click();
  await expect(
    page.getByRole("heading", { name: "Sign in to Kanban Studio" })
  ).toBeVisible();
});
