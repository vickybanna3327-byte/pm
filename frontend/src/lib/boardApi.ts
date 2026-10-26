import type { BoardData } from "@/lib/kanban";

const BOARD_URL = "/api/users/user/board";

const isBoardData = (value: unknown): value is BoardData => {
  if (!value || typeof value !== "object") {
    return false;
  }
  const board = value as Record<string, unknown>;
  if (
    !Array.isArray(board.columns) ||
    !board.cards ||
    typeof board.cards !== "object" ||
    Array.isArray(board.cards)
  ) {
    return false;
  }
  const columnIds = new Set<string>();
  const cardIds = new Set<string>();
  const columnsAreValid = board.columns.every((column: unknown) => {
    if (!column || typeof column !== "object") {
      return false;
    }
    const item = column as Record<string, unknown>;
    if (
      typeof item.id === "string" &&
      typeof item.title === "string" &&
      Array.isArray(item.cardIds) &&
      !columnIds.has(item.id)
    ) {
      columnIds.add(item.id);
      return item.cardIds.every((cardId: unknown) => {
        if (
          typeof cardId !== "string" ||
          cardIds.has(cardId) ||
          !Object.prototype.hasOwnProperty.call(board.cards, cardId)
        ) {
          return false;
        }
        cardIds.add(cardId);
        return true;
      });
    }
    return false;
  });
  const cardsAreValid = Object.entries(board.cards).every(([id, card]) => {
    if (!card || typeof card !== "object") {
      return false;
    }
    const item = card as Record<string, unknown>;
    return (
      item.id === id &&
      typeof item.title === "string" &&
      typeof item.details === "string"
    );
  });
  return (
    columnsAreValid &&
    cardsAreValid &&
    cardIds.size === Object.keys(board.cards).length
  );
};

const requestBoard = async (
  path = "",
  init?: RequestInit
): Promise<BoardData> => {
  const response = await fetch(`${BOARD_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    const body: unknown = await response.json();
    const detail =
      body && typeof body === "object" && "detail" in body
        ? String(body.detail)
        : response.statusText;
    throw new Error(detail || `Request failed (${response.status}).`);
  }

  const result: unknown = await response.json();
  if (!isBoardData(result)) {
    throw new Error("The server returned an invalid board.");
  }
  return result;
};

export const fetchBoard = () => requestBoard();

export const renameColumn = (columnId: string, title: string) =>
  requestBoard(`/columns/${encodeURIComponent(columnId)}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });

export const createCard = (
  columnId: string,
  title: string,
  details: string
) =>
  requestBoard(`/columns/${encodeURIComponent(columnId)}/cards`, {
    method: "POST",
    body: JSON.stringify({ title, details }),
  });

export const deleteCard = (cardId: string) =>
  requestBoard(`/cards/${encodeURIComponent(cardId)}`, {
    method: "DELETE",
  });

export const updateCard = (cardId: string, title: string, details: string) =>
  requestBoard(`/cards/${encodeURIComponent(cardId)}`, {
    method: "PATCH",
    body: JSON.stringify({ title, details }),
  });

export const moveCard = (
  cardId: string,
  columnId: string,
  position?: number
) =>
  requestBoard(`/cards/${encodeURIComponent(cardId)}/move`, {
    method: "POST",
    body: JSON.stringify({
      column_id: columnId,
      ...(position === undefined ? {} : { position }),
    }),
  });
