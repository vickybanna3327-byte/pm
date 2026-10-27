import type { BoardData } from "@/lib/kanban";
import * as boardApi from "@/lib/boardApi";
import type { BoardChatResponse, ChatMessage } from "@/lib/boardApi";

export type BoardState = {
  board: BoardData | null;
  status: "loading" | "ready" | "error";
  error: string | null;
  saving: boolean;
};

const BOARD_CHANGE_EVENT = "pm-mvp-board-change";
const EMPTY_STATE: BoardState = {
  board: null,
  status: "loading",
  error: null,
  saving: false,
};

let state = EMPTY_STATE;
let mutationQueue: Promise<void> = Promise.resolve();

const notify = () => window.dispatchEvent(new Event(BOARD_CHANGE_EVENT));

const setState = (nextState: BoardState) => {
  state = nextState;
  notify();
};

export const subscribeToBoard = (onChange: () => void) => {
  window.addEventListener(BOARD_CHANGE_EVENT, onChange);
  return () => window.removeEventListener(BOARD_CHANGE_EVENT, onChange);
};

export const getBoardSnapshot = () => state;
export const getServerBoardSnapshot = () => EMPTY_STATE;

export const loadBoard = async (projectId: string | null = null) => {
  boardApi.setActiveProjectId(projectId);
  setState({ board: null, status: "loading", error: null, saving: false });
  try {
    const board = await boardApi.fetchBoard();
    setState({ board, status: "ready", error: null, saving: false });
  } catch (error) {
    setState({
      board: null,
      status: "error",
      error: error instanceof Error ? error.message : "Unable to load the board.",
      saving: false,
    });
  }
};

const saveMutation = (mutation: () => Promise<BoardData>) => {
  const nextMutation = mutationQueue.then(async () => {
    setState({ ...state, error: null, saving: true });
    try {
      const board = await mutation();
      setState({ board, status: "ready", error: null, saving: false });
    } catch (error) {
      setState({
        ...state,
        error:
          error instanceof Error ? error.message : "Unable to save board changes.",
        saving: false,
      });
    }
  });
  mutationQueue = nextMutation;
  return nextMutation;
};

export const saveColumnRename = (columnId: string, title: string) =>
  saveMutation(() => boardApi.renameColumn(columnId, title));

export const saveCardCreate = (
  columnId: string,
  title: string,
  details: string
) => saveMutation(() => boardApi.createCard(columnId, title, details));

export const saveCardDelete = (cardId: string) =>
  saveMutation(() => boardApi.deleteCard(cardId));

export const saveCardUpdate = (cardId: string, title: string, details: string) =>
  saveMutation(() => boardApi.updateCard(cardId, title, details));

export const saveCardMove = (
  cardId: string,
  columnId: string,
  position?: number
) => saveMutation(() => boardApi.moveCard(cardId, columnId, position));

export const sendBoardChat = (
  question: string,
  history: ChatMessage[]
): Promise<BoardChatResponse> => {
  const chatRequest = mutationQueue.then(async () => {
    try {
      const result = await boardApi.chatWithBoard(question, history);
      setState({
        board: result.board,
        status: "ready",
        error: null,
        saving: false,
      });
      return result;
    } catch (error) {
      setState({ ...state, saving: false });
      throw error;
    }
  });
  mutationQueue = chatRequest.then(
    () => undefined,
    () => undefined
  );
  return chatRequest;
};
