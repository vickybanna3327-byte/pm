# Frontend AGENTS.md

## Purpose

This directory contains the Next.js frontend for the project management MVP. The app is a single-board Kanban interface that is statically exported and served by the Python FastAPI backend. Board data is loaded from and persisted to the backend's SQLite database.

## Current architecture

### App entry and render path
- `src/app/page.tsx` is the root page for `/`.
- It renders `AuthGate`, which gates the board behind the MVP sign-in flow.
- `next.config.ts` enables static export; `npm run build` writes the production site to `out/`.

### Key frontend modules
- `src/components/KanbanBoard.tsx`
  - Main board container.
  - Loads the board and renders loading, error, and save status.
  - Coordinates board operations with the external board store.
  - Uses `@dnd-kit` for drag interactions.
  - Persists column renames, card creation/editing/deletion, and card movement.
- `src/components/AuthGate.tsx`
  - Gates the demo board behind the hardcoded MVP credentials.
  - Stores the signed-in flag in `sessionStorage`, so it lasts only for the current tab session.
  - This is a frontend demo gate, not production authentication.
- `src/lib/sessionBoard.ts`
  - Maintains the loaded board and loading/error/saving status in a small external store.
  - Serializes mutations so each response is applied in request order.
- `src/lib/boardApi.ts`
  - Calls the FastAPI board endpoints, including card editing, and validates the returned `BoardData` shape.
  - Reports HTTP, network, and invalid-response errors to the board store.
- `src/components/KanbanColumn.tsx`
  - Renders a single board column.
  - Handles droppable regions and card lists within each column.
  - Uses a `NewCardForm` for adding cards.
- `src/components/KanbanCard.tsx`
  - Displays a card and its details.
  - Supports editing title/details and deleting cards.
- `src/components/KanbanCardPreview.tsx`
  - Small drag preview component used while a card is being dragged.
- `src/components/NewCardForm.tsx`
  - Inline card-creation form used inside each column.

### Shared board model
- `src/lib/kanban.ts` defines the app’s core board data model.
- Types:
  - `Card`: `{ id, title, details }`
  - `Column`: `{ id, title, cardIds }`
  - `BoardData`: `{ columns, cards }`
- `initialData` defines the demo board used by backend database seeding and frontend tests.
- `moveCard` handles moving cards between columns and reordering within the same column.
- `createId` generates new card IDs.

## Existing behaviors

The current frontend already includes:
- a fixed column layout
- renameable columns
- card creation and deletion
- drag-and-drop card movement
- board state persisted in SQLite through the FastAPI API
- loading, retry, save-progress, and save-error feedback

## Testing strategy

The project already includes a Vitest and Playwright setup:
- `src/lib/kanban.test.ts` contains unit tests around board movement logic.
- `src/lib/sessionBoard.test.ts` checks API URLs, methods, payloads, malformed responses, and store error handling.
- `src/components/KanbanBoard.test.tsx` checks board rendering and maps user actions to API mutations.
- `playwright.config.ts` and `tests/kanban.spec.ts` cover browser flows using a stateful API mock, including reload and logout/sign-in persistence.
- Backend route tests and a live Docker/browser check validate the actual frontend/backend/SQLite integration.
- `npm run test:unit` runs Vitest and reports coverage for frontend components and board logic.

Testing expectations for future work:
- Prefer small unit tests for pure board logic in `src/lib`.
- Prefer component tests for interactions such as card creation, login gating, and board updates.
- Prefer browser integration tests for the core user journeys and validate the actual Docker-served app against SQLite for cross-layer changes.
- Prioritize tests for meaningful behavior and failure cases. Treat 80% coverage as a useful target when sensible, not a gate; do not add tests solely to inflate the percentage.

## Styling and design system

The frontend uses a simple design system based on CSS variables and utility classes:
- Accent Yellow: `#ecad0a`
- Blue Primary: `#209dd7`
- Purple Secondary: `#753991`
- Dark Navy: `#032147`
- Gray Text: `#888888`

The app is built with Next.js App Router and TypeScript, and it relies on utility-class styling rather than a large component library.

## Constraints and conventions

- Keep the implementation simple and direct; do not add unnecessary abstraction layers.
- Preserve the existing front-end demo structure unless the task explicitly requires architectural changes.
- Keep server-loaded board state in `sessionBoard.ts`; do not use browser storage as the source of truth for board data.
- Keep the API contract consistent with the existing `BoardData` shape.
- Prefer existing patterns and test conventions before introducing new tooling or framework patterns.

## Expected future work

This directory will eventually be adapted to integrate with the AI chat sidebar and its board mutation flow. The current sign-in remains a frontend-only demo gate and is not backend authentication.

Use this file as the working reference for the current frontend implementation and update it whenever the architecture changes significantly.
