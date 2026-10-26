import type { ReactNode } from "react";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { KanbanBoard } from "@/components/KanbanBoard";
import * as boardApi from "@/lib/boardApi";
import { initialData } from "@/lib/kanban";

const apiMocks = vi.hoisted(() => ({
  fetchBoard: vi.fn(),
  renameColumn: vi.fn(),
  createCard: vi.fn(),
  deleteCard: vi.fn(),
  moveCard: vi.fn(),
}));

vi.mock("@/lib/boardApi", () => apiMocks);

vi.mock("@dnd-kit/core", () => ({
  DndContext: ({
    children,
    onDragStart,
    onDragEnd,
  }: {
    children: ReactNode;
    onDragStart: (event: { active: { id: string } }) => void;
    onDragEnd: (event: {
      active: { id: string };
      over: { id: string } | null;
    }) => void;
  }) => (
    <div>
      <button
        data-testid="drag-start"
        onClick={() => onDragStart({ active: { id: "card-1" } })}
      />
      <button
        data-testid="drag-no-target"
        onClick={() =>
          onDragEnd({ active: { id: "card-1" }, over: null })
        }
      />
      <button
        data-testid="drag-self"
        onClick={() =>
          onDragEnd({
            active: { id: "card-1" },
            over: { id: "card-1" },
          })
        }
      />
      <button
        data-testid="drag-to-review"
        onClick={() =>
          onDragEnd({
            active: { id: "card-1" },
            over: { id: "card-6" },
          })
        }
      />
      {children}
    </div>
  ),
  DragOverlay: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  PointerSensor: () => null,
  closestCorners: () => null,
  useDroppable: () => ({ setNodeRef: () => {}, isOver: false }),
  useSensor: () => null,
  useSensors: (...sensors: unknown[]) => sensors,
}));

vi.mock("@dnd-kit/sortable", () => ({
  SortableContext: ({ children }: { children: ReactNode }) => <>{children}</>,
  verticalListSortingStrategy: {},
  useSortable: () => ({
    attributes: {},
    listeners: {},
    setNodeRef: () => {},
    transform: null,
    transition: undefined,
    isDragging: false,
  }),
}));

vi.mock("@dnd-kit/utilities", () => ({
  CSS: { Transform: { toString: () => undefined } },
}));

const getFirstColumn = async () =>
  (await screen.findAllByTestId(/column-/i))[0];
const renderBoard = () => render(<KanbanBoard onLogout={() => {}} />);

describe("KanbanBoard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMocks.fetchBoard.mockResolvedValue(structuredClone(initialData));
    apiMocks.renameColumn.mockResolvedValue(structuredClone(initialData));
    apiMocks.createCard.mockResolvedValue(structuredClone(initialData));
    apiMocks.deleteCard.mockResolvedValue(structuredClone(initialData));
    apiMocks.moveCard.mockResolvedValue(structuredClone(initialData));
  });

  it("loads and renders five columns", async () => {
    renderBoard();
    expect(await screen.findAllByTestId(/column-/i)).toHaveLength(5);
  });

  it("renames a column", async () => {
    renderBoard();
    const column = await getFirstColumn();
    await within(column).findByLabelText("Column title");
    const input = within(column).getByLabelText("Column title");
    await userEvent.clear(input);
    await userEvent.type(input, "New Name");
    fireEvent.blur(input);
    await waitFor(() =>
      expect(boardApi.renameColumn).toHaveBeenLastCalledWith(
        "col-backlog",
        "New Name"
      )
    );
  });

  it("adds and removes a card", async () => {
    renderBoard();
    const column = await getFirstColumn();
    await within(column).findByRole("button", { name: /add a card/i });
    const addButton = within(column).getByRole("button", {
      name: /add a card/i,
    });
    await userEvent.click(addButton);

    const titleInput = within(column).getByPlaceholderText(/card title/i);
    await userEvent.type(titleInput, "New card");
    const detailsInput = within(column).getByPlaceholderText(/details/i);
    await userEvent.type(detailsInput, "Notes");

    await userEvent.click(within(column).getByRole("button", { name: /add card/i }));

    await waitFor(() =>
      expect(boardApi.createCard).toHaveBeenCalledWith(
        "col-backlog",
        "New card",
        "Notes"
      )
    );
  });

  it("shows a drag preview and requests a card move", async () => {
    renderBoard();
    await screen.findByTestId("card-card-1");
    fireEvent.click(screen.getByTestId("drag-start"));

    expect(
      screen.getAllByText(
        "Draft quarterly themes with impact statements and metrics."
      )
    ).toHaveLength(2);

    fireEvent.click(screen.getByTestId("drag-to-review"));
    await waitFor(() =>
      expect(boardApi.moveCard).toHaveBeenCalledWith(
        "card-1",
        "col-review",
        0
      )
    );
  });

  it("does not request a move when dropped without a target or on itself", async () => {
    renderBoard();
    await screen.findByTestId("card-card-1");

    fireEvent.click(screen.getByTestId("drag-no-target"));
    fireEvent.click(screen.getByTestId("drag-self"));
    expect(boardApi.moveCard).not.toHaveBeenCalled();
  });

  it("requests card deletion", async () => {
    renderBoard();
    const card = await screen.findByTestId("card-card-1");
    await userEvent.click(
      within(card).getByRole("button", { name: "Delete Align roadmap themes" })
    );
    expect(boardApi.deleteCard).toHaveBeenCalledWith("card-1");
  });

});
