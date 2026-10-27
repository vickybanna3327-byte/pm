import type { ReactNode } from "react";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { KanbanBoard } from "@/components/KanbanBoard";
import type { AuthUser } from "@/lib/authApi";
import * as boardApi from "@/lib/boardApi";
import { initialData } from "@/lib/kanban";

const apiMocks = vi.hoisted(() => ({
  fetchBoard: vi.fn(),
  renameColumn: vi.fn(),
  createCard: vi.fn(),
  deleteCard: vi.fn(),
  updateCard: vi.fn(),
  moveCard: vi.fn(),
  chatWithBoard: vi.fn(),
  setActiveProjectId: vi.fn(),
  changePassword: vi.fn(),
}));

vi.mock("@/lib/boardApi", () => apiMocks);
vi.mock("@/lib/authApi", () => ({
  changePassword: apiMocks.changePassword,
}));

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
const testUser: AuthUser = {
  id: "test-user",
  username: "testuser",
  email: "test@example.com",
  full_name: "Test User",
  role: "member",
};
const renderBoard = () =>
  render(<KanbanBoard onLogout={() => {}} currentUser={testUser} />);

describe("KanbanBoard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMocks.fetchBoard.mockResolvedValue(structuredClone(initialData));
    apiMocks.renameColumn.mockResolvedValue(structuredClone(initialData));
    apiMocks.createCard.mockResolvedValue(structuredClone(initialData));
    apiMocks.deleteCard.mockResolvedValue(structuredClone(initialData));
    apiMocks.updateCard.mockResolvedValue(structuredClone(initialData));
    apiMocks.moveCard.mockResolvedValue(structuredClone(initialData));
    apiMocks.chatWithBoard.mockResolvedValue({
      model: "openai/gpt-oss-120b",
      reply: "There are eight cards.",
      board: structuredClone(initialData),
      changed: false,
    });
    apiMocks.changePassword.mockResolvedValue({ message: "Password updated." });
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

  it("submits edits to a card's title and details", async () => {
    renderBoard();
    const card = await screen.findByTestId("card-card-1");
    await userEvent.click(
      within(card).getByRole("button", { name: "Edit Align roadmap themes" })
    );
    await userEvent.clear(
      within(card).getByRole("textbox", {
        name: "Edit title for Align roadmap themes",
      })
    );
    await userEvent.type(
      within(card).getByRole("textbox", {
        name: "Edit title for Align roadmap themes",
      }),
      "Updated roadmap"
    );
    await userEvent.clear(
      within(card).getByRole("textbox", {
        name: "Edit details for Align roadmap themes",
      })
    );
    await userEvent.type(
      within(card).getByRole("textbox", {
        name: "Edit details for Align roadmap themes",
      }),
      "Updated details"
    );
    await userEvent.click(
      within(card).getByRole("button", { name: "Save changes" })
    );

    await waitFor(() =>
      expect(boardApi.updateCard).toHaveBeenCalledWith(
        "card-1",
        "Updated roadmap",
        "Updated details"
      )
    );
  });

  it("sends chat history and applies the returned board", async () => {
    const updatedBoard = structuredClone(initialData);
    updatedBoard.columns[0].cardIds = ["card-2", "card-1"];
    apiMocks.chatWithBoard
      .mockResolvedValueOnce({
        model: "openai/gpt-oss-120b",
        reply: "There are eight cards.",
        board: structuredClone(initialData),
        changed: false,
      })
      .mockResolvedValueOnce({
        model: "openai/gpt-oss-120b",
        reply: "Moved the roadmap card.",
        board: updatedBoard,
        changed: true,
      });

    renderBoard();
    await screen.findByTestId("card-card-1");
    const message = screen.getByLabelText("Message the board assistant");
    await userEvent.type(message, "How many cards?");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("There are eight cards.")).toBeVisible();
    await userEvent.clear(message);
    await userEvent.type(message, "Move the roadmap card.");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("Moved the roadmap card.")).toBeVisible();
    expect(
      within(screen.getByTestId("column-col-backlog")).getAllByTestId(
        /^card-card-/
      )[0]
    ).toHaveAttribute("data-testid", "card-card-2");
    await waitFor(() =>
      expect(apiMocks.chatWithBoard).toHaveBeenLastCalledWith(
        "Move the roadmap card.",
        [
          { role: "user", content: "How many cards?" },
          { role: "assistant", content: "There are eight cards." },
        ]
      )
    );
    expect(
      within(screen.getByRole("log", { name: "Conversation" })).getByText(
        "How many cards?"
      )
    ).toBeVisible();
  });

  it("shows chat errors without clearing the draft", async () => {
    apiMocks.chatWithBoard.mockRejectedValueOnce(
      new Error("OpenRouter is not configured.")
    );
    renderBoard();
    await screen.findByTestId("card-card-1");
    const message = screen.getByLabelText("Message the board assistant");
    await userEvent.type(message, "Please review this board.");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "OpenRouter is not configured."
    );
    expect(message).toHaveValue("Please review this board.");
  });

  it("shows account details and changes the password", async () => {
    renderBoard();
    await screen.findByTestId("card-card-1");
    await userEvent.click(screen.getByRole("button", { name: "Test User" }));
    expect(screen.getByText("test@example.com")).toBeVisible();
    await userEvent.type(
      screen.getByLabelText("Current password"),
      "OldSecurePassword123!"
    );
    await userEvent.type(
      screen.getByLabelText("New password"),
      "NewSecurePassword123!"
    );
    await userEvent.type(
      screen.getByLabelText("Confirm new password"),
      "NewSecurePassword123!"
    );
    await userEvent.click(screen.getByRole("button", { name: "Update password" }));

    await waitFor(() =>
      expect(apiMocks.changePassword).toHaveBeenCalledWith(
        "OldSecurePassword123!",
        "NewSecurePassword123!"
      )
    );
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Password updated."
    );
  });

});
