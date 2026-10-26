import { initialData, type BoardData } from "@/lib/kanban";

const BOARD_STORAGE_KEY = "pm-mvp-board";
const BOARD_CHANGE_EVENT = "pm-mvp-board-change";

let cachedSerializedBoard: string | null | undefined;
let cachedBoard: BoardData = initialData;

export const subscribeToBoard = (onChange: () => void) => {
  window.addEventListener(BOARD_CHANGE_EVENT, onChange);
  return () => window.removeEventListener(BOARD_CHANGE_EVENT, onChange);
};

export const getBoardSnapshot = () => {
  const serializedBoard = sessionStorage.getItem(BOARD_STORAGE_KEY);
  if (serializedBoard !== cachedSerializedBoard) {
    cachedSerializedBoard = serializedBoard;
    cachedBoard = serializedBoard
      ? JSON.parse(serializedBoard)
      : initialData;
  }
  return cachedBoard;
};

export const getServerBoardSnapshot = () => initialData;

export const updateSessionBoard = (
  update: (board: BoardData) => BoardData
) => {
  const nextBoard = update(getBoardSnapshot());
  const serializedBoard = JSON.stringify(nextBoard);

  sessionStorage.setItem(BOARD_STORAGE_KEY, serializedBoard);
  cachedSerializedBoard = serializedBoard;
  cachedBoard = nextBoard;
  window.dispatchEvent(new Event(BOARD_CHANGE_EVENT));
};
