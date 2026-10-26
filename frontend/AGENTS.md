# Frontend AGENTS.md

## Purpose

This directory contains the Next.js frontend for the project management MVP. The app is a single-board Kanban demo that is statically exported and served by the Python FastAPI backend. It will eventually integrate with the backend API and OpenRouter AI backend.

## Current architecture

### App entry and render path
- `src/app/page.tsx` is the root page for `/`.
- It renders `AuthGate`, which gates the board behind the MVP sign-in flow.
- `next.config.ts` enables static export; `npm run build` writes the production site to `out/`.

### Key frontend modules
- `src/components/KanbanBoard.tsx`
  - Main board container.
  - Owns the board state and card drag-and-drop behavior.
  - Uses `@dnd-kit` for drag interactions.
  - Renames columns, adds cards, and deletes cards.
- `src/components/AuthGate.tsx`
  - Gates the demo board behind the hardcoded MVP credentials.
  - Stores the signed-in flag in `sessionStorage`, so it lasts only for the current tab session.
  - This is a frontend demo gate, not production authentication.
- `src/lib/sessionBoard.ts`
  - Stores board edits in `sessionStorage` and shares updates with the mounted board through a small external-store subscription.
  - Board edits remain available after signing out and back in within the same tab session.
- `src/components/KanbanColumn.tsx`
  - Renders a single board column.
  - Handles droppable regions and card lists within each column.
  - Uses a `NewCardForm` for adding cards.
- `src/components/KanbanCard.tsx`
  - Displays a card and its details.
  - Includes card deletion behavior.
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
- `initialData` is the default board seeded with a small demo set of cards and columns.
- `moveCard` handles moving cards between columns and reordering within the same column.
- `createId` generates new card IDs.

## Existing behaviors

The current frontend already includes:
- a fixed column layout
- renameable columns
- card creation and deletion
- drag-and-drop card movement
- a sample board with realistic card content and styling

## Testing strategy

The project already includes a Vitest and Playwright setup:
- `src/lib/kanban.test.ts` contains unit tests around board movement logic.
- `src/components/KanbanBoard.test.tsx` is part of the frontend test suite and should be kept aligned with UI changes.
- `playwright.config.ts` and `tests/kanban.spec.ts` cover browser-level integration checks.
- `npm run test:unit` runs Vitest and reports coverage for frontend components and board logic.

Testing expectations for future work:
- Prefer small unit tests for pure board logic in `src/lib`.
- Prefer component tests for interactions such as card creation, login gating, and board updates.
- Prefer browser integration tests for the core user journeys.
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
- Do not move state outside the board unless required by the current phase.
- When adding backend integration, keep the board contract consistent with the existing `BoardData` shape.
- Prefer existing patterns and test conventions before introducing new tooling or framework patterns.

## Expected future work

This directory will eventually be adapted to:
- serve the app behind the Python backend
- enforce a dummy sign-in gate
- read and write board data from the backend database
- integrate with the AI chat sidebar and mutation flow

Use this file as the working reference for the current frontend implementation and update it whenever the architecture changes significantly.
