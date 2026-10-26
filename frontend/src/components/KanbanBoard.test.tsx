import type { ReactNode } from "react";
import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { KanbanBoard } from "@/components/KanbanBoard";

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
            over: { id: "col-review" },
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

const getFirstColumn = () => screen.getAllByTestId(/column-/i)[0];
const renderBoard = () => render(<KanbanBoard onLogout={() => {}} />);

describe("KanbanBoard", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it("renders five columns", () => {
    renderBoard();
    expect(screen.getAllByTestId(/column-/i)).toHaveLength(5);
  });

  it("renames a column", async () => {
    renderBoard();
    const column = getFirstColumn();
    const input = within(column).getByLabelText("Column title");
    await userEvent.clear(input);
    await userEvent.type(input, "New Name");
    expect(input).toHaveValue("New Name");
  });

  it("adds and removes a card", async () => {
    renderBoard();
    const column = getFirstColumn();
    const addButton = within(column).getByRole("button", {
      name: /add a card/i,
    });
    await userEvent.click(addButton);

    const titleInput = within(column).getByPlaceholderText(/card title/i);
    await userEvent.type(titleInput, "New card");
    const detailsInput = within(column).getByPlaceholderText(/details/i);
    await userEvent.type(detailsInput, "Notes");

    await userEvent.click(within(column).getByRole("button", { name: /add card/i }));

    expect(within(column).getByText("New card")).toBeInTheDocument();

    const deleteButton = within(column).getByRole("button", {
      name: /delete new card/i,
    });
    await userEvent.click(deleteButton);

    expect(within(column).queryByText("New card")).not.toBeInTheDocument();
  });

  it("shows a drag preview and moves a card to another column", () => {
    renderBoard();
    fireEvent.click(screen.getByTestId("drag-start"));

    expect(
      screen.getAllByText(
        "Draft quarterly themes with impact statements and metrics."
      )
    ).toHaveLength(2);

    fireEvent.click(screen.getByTestId("drag-to-review"));
    expect(
      within(screen.getByTestId("column-col-review")).getByTestId(
        "card-card-1"
      )
    ).toBeInTheDocument();
  });

  it("does not move a card when dropped without a target or on itself", () => {
    renderBoard();
    const firstColumn = screen.getByTestId("column-col-backlog");

    fireEvent.click(screen.getByTestId("drag-no-target"));
    expect(within(firstColumn).getByTestId("card-card-1")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("drag-self"));
    expect(within(firstColumn).getByTestId("card-card-1")).toBeInTheDocument();
  });

});
