import { getBoardSnapshot, updateSessionBoard } from "@/lib/sessionBoard";
import { initialData } from "@/lib/kanban";

describe("session board storage", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it("starts with the demo board when there is no saved board", () => {
    expect(getBoardSnapshot()).toEqual(initialData);
  });

  it("saves board updates for the current browser session", () => {
    updateSessionBoard((board) => ({
      ...board,
      columns: board.columns.map((column) =>
        column.id === "col-backlog"
          ? { ...column, cardIds: ["card-2"] }
          : column
      ),
    }));

    expect(getBoardSnapshot().columns[0].cardIds).toEqual(["card-2"]);
    expect(JSON.parse(sessionStorage.getItem("pm-mvp-board") ?? "{}")).toEqual(
      getBoardSnapshot()
    );
  });
});
