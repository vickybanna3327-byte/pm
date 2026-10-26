import {
  createCard,
  deleteCard,
  fetchBoard,
  moveCard,
  renameColumn,
  updateCard,
} from "@/lib/boardApi";
import { initialData } from "@/lib/kanban";
import { getBoardSnapshot, loadBoard, saveColumnRename } from "@/lib/sessionBoard";

const response = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

describe("board API", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads a valid board from the user board endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(initialData));
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchBoard()).resolves.toEqual(initialData);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/users/user/board",
      expect.objectContaining({ headers: { "Content-Type": "application/json" } })
    );
  });

  it("sends column renames as JSON patches", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(initialData));
    vi.stubGlobal("fetch", fetchMock);

    await renameColumn("col-backlog", "Queued");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/users/user/board/columns/col-backlog",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ title: "Queued" }),
      })
    );
  });

  it("sends card mutations using the backend contract", async () => {
    const fetchMock = vi.fn().mockImplementation(async () => response(initialData));
    vi.stubGlobal("fetch", fetchMock);

    await createCard("col-backlog", "New task", "Task details");
    expect(fetchMock).toHaveBeenLastCalledWith(
      "/api/users/user/board/columns/col-backlog/cards",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ title: "New task", details: "Task details" }),
      })
    );

    await deleteCard("card-1");
    expect(fetchMock).toHaveBeenLastCalledWith(
      "/api/users/user/board/cards/card-1",
      expect.objectContaining({ method: "DELETE" })
    );

    await updateCard("card-1", "Updated task", "Updated details");
    expect(fetchMock).toHaveBeenLastCalledWith(
      "/api/users/user/board/cards/card-1",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({
          title: "Updated task",
          details: "Updated details",
        }),
      })
    );

    await moveCard("card-1", "col-review", 0);
    expect(fetchMock).toHaveBeenLastCalledWith(
      "/api/users/user/board/cards/card-1/move",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ column_id: "col-review", position: 0 }),
      })
    );
  });

  it("reports server errors and rejects invalid board responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(response({ detail: "Board not found." }, 404))
        .mockResolvedValueOnce(
          response({ columns: [], cards: { orphan: { id: "orphan" } } })
        )
    );

    await expect(fetchBoard()).rejects.toThrow("Board not found.");
    await expect(fetchBoard()).rejects.toThrow("invalid board");
  });
});

describe("board loading state", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads backend state into the board store", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(initialData)));

    await loadBoard();

    expect(getBoardSnapshot()).toMatchObject({
      board: initialData,
      status: "ready",
      error: null,
    });
  });

  it("surfaces load and mutation errors instead of hiding them", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(response({ detail: "Backend unavailable." }, 503))
        .mockResolvedValueOnce(response({ detail: "Update rejected." }, 400))
    );

    await loadBoard();
    expect(getBoardSnapshot()).toMatchObject({
      status: "error",
      error: "Backend unavailable.",
    });

    await saveColumnRename("col-backlog", "Queued");
    expect(getBoardSnapshot().error).toBe("Update rejected.");
  });
});
