"use client";

import { useEffect, useMemo, useState, useSyncExternalStore } from "react";
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  closestCorners,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { KanbanColumn } from "@/components/KanbanColumn";
import { KanbanCardPreview } from "@/components/KanbanCardPreview";
import {
  getBoardSnapshot,
  getServerBoardSnapshot,
  loadBoard,
  saveCardCreate,
  saveCardDelete,
  saveCardMove,
  saveColumnRename,
  subscribeToBoard,
} from "@/lib/sessionBoard";

export const KanbanBoard = ({ onLogout }: { onLogout: () => void }) => {
  const boardState = useSyncExternalStore(
    subscribeToBoard,
    getBoardSnapshot,
    getServerBoardSnapshot
  );
  const [activeCardId, setActiveCardId] = useState<string | null>(null);
  const board = boardState.board;

  useEffect(() => {
    void loadBoard();
  }, []);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 6 },
    })
  );

  const cardsById = useMemo(() => board?.cards ?? {}, [board?.cards]);

  const handleDragStart = (event: DragStartEvent) => {
    setActiveCardId(event.active.id as string);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveCardId(null);

    if (!over || active.id === over.id) {
      return;
    }

    const cardId = String(active.id);
    const targetId = String(over.id);
    const targetColumn = board?.columns.find(
      (column) =>
        column.id === targetId || column.cardIds.includes(targetId)
    );
    if (targetColumn) {
      const targetIndex = targetColumn.cardIds.indexOf(targetId);
      const activeIndex = targetColumn.cardIds.indexOf(cardId);
      const droppedOnColumn = targetId === targetColumn.id;
      const position = droppedOnColumn
        ? targetColumn.cardIds.length - (activeIndex !== -1 ? 1 : 0)
        : targetIndex - (activeIndex !== -1 && activeIndex < targetIndex ? 1 : 0);
      void saveCardMove(cardId, targetColumn.id, position);
    }
  };

  const handleRenameColumn = (columnId: string, title: string) => {
    void saveColumnRename(columnId, title);
  };

  const handleAddCard = (columnId: string, title: string, details: string) => {
    void saveCardCreate(columnId, title, details || "No details yet.");
  };

  const handleDeleteCard = (_columnId: string, cardId: string) => {
    void saveCardDelete(cardId);
  };

  if (boardState.status === "loading") {
    return (
      <main
        aria-label="Loading board"
        aria-busy="true"
        className="flex min-h-screen items-center justify-center text-sm font-semibold text-[var(--gray-text)]"
      >
        Loading your board...
      </main>
    );
  }

  if (boardState.status === "error" || !board) {
    return (
      <main className="flex min-h-screen items-center justify-center px-6">
        <section className="max-w-md rounded-3xl border border-[var(--stroke)] bg-white p-8 shadow-[var(--shadow)]">
          <h1 className="font-display text-2xl font-semibold text-[var(--navy-dark)]">
            Could not load your board
          </h1>
          <p role="alert" className="mt-3 text-sm text-[var(--gray-text)]">
            {boardState.error}
          </p>
          <button
            type="button"
            onClick={() => void loadBoard()}
            className="mt-6 rounded-full bg-[var(--secondary-purple)] px-5 py-3 text-sm font-semibold text-white"
          >
            Try again
          </button>
          <button
            type="button"
            onClick={onLogout}
            className="ml-3 rounded-full border border-[var(--stroke)] px-5 py-3 text-sm font-semibold text-[var(--navy-dark)]"
          >
            Log out
          </button>
        </section>
      </main>
    );
  }

  const activeCard = activeCardId ? cardsById[activeCardId] : null;

  return (
    <div className="relative overflow-hidden">
      <div className="pointer-events-none absolute left-0 top-0 h-[420px] w-[420px] -translate-x-1/3 -translate-y-1/3 rounded-full bg-[radial-gradient(circle,_rgba(32,157,215,0.25)_0%,_rgba(32,157,215,0.05)_55%,_transparent_70%)]" />
      <div className="pointer-events-none absolute bottom-0 right-0 h-[520px] w-[520px] translate-x-1/4 translate-y-1/4 rounded-full bg-[radial-gradient(circle,_rgba(117,57,145,0.18)_0%,_rgba(117,57,145,0.05)_55%,_transparent_75%)]" />

      <main className="relative mx-auto flex min-h-screen max-w-[1500px] flex-col gap-10 px-6 pb-16 pt-12">
        <header className="flex flex-col gap-6 rounded-[32px] border border-[var(--stroke)] bg-white/80 p-8 shadow-[var(--shadow)] backdrop-blur">
          {boardState.error && (
            <p role="alert" className="text-sm font-medium text-red-700">
              Could not save board changes: {boardState.error}
            </p>
          )}
          {boardState.saving && (
            <p role="status" className="text-sm text-[var(--gray-text)]">
              Saving board...
            </p>
          )}
          <div className="flex flex-wrap items-start justify-between gap-6">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.35em] text-[var(--gray-text)]">
                Single Board Kanban
              </p>
              <h1 className="mt-3 font-display text-4xl font-semibold text-[var(--navy-dark)]">
                Kanban Studio
              </h1>
              <p className="mt-3 max-w-xl text-sm leading-6 text-[var(--gray-text)]">
                Keep momentum visible. Rename columns, drag cards between stages,
                and capture quick notes without getting buried in settings.
              </p>
            </div>
            <div className="flex flex-wrap items-start gap-3">
              <div className="rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] px-5 py-4">
                <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--gray-text)]">
                  Focus
                </p>
                <p className="mt-2 text-lg font-semibold text-[var(--primary-blue)]">
                  One board. Five columns. Zero clutter.
                </p>
              </div>
              <button
                type="button"
                onClick={onLogout}
                className="rounded-full border border-[var(--stroke)] px-4 py-2 text-sm font-semibold text-[var(--navy-dark)] transition hover:border-[var(--primary-blue)] hover:text-[var(--primary-blue)]"
              >
                Log out
              </button>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-4">
            {board.columns.map((column) => (
              <div
                key={column.id}
                className="flex items-center gap-2 rounded-full border border-[var(--stroke)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--navy-dark)]"
              >
                <span className="h-2 w-2 rounded-full bg-[var(--accent-yellow)]" />
                {column.title}
              </div>
            ))}
          </div>
        </header>

        <DndContext
          sensors={sensors}
          collisionDetection={closestCorners}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
        >
          <section className="grid gap-6 lg:grid-cols-5">
            {board.columns.map((column) => (
              <KanbanColumn
                key={column.id}
                column={column}
                cards={column.cardIds.map((cardId) => board.cards[cardId])}
                onRename={handleRenameColumn}
                onAddCard={handleAddCard}
                onDeleteCard={handleDeleteCard}
              />
            ))}
          </section>
          <DragOverlay>
            {activeCard ? (
              <div className="w-[260px]">
                <KanbanCardPreview card={activeCard} />
              </div>
            ) : null}
          </DragOverlay>
        </DndContext>
      </main>
    </div>
  );
};
