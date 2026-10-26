# Project plan for the PM MVP

## Part 1: Planning and approval gate

Goal: confirm the project direction, capture the work breakdown, and set explicit definition-of-done criteria before implementing any production code.

Checklist:
- [x] Confirm the project requirements from the top-level AGENTS.md and the business requirements documented in this repo.
- [x] Review the existing frontend demo and identify what is already implemented versus what must be built for the MVP.
- [x] Write a detailed execution plan for each project phase, including subtasks, validation, and acceptance criteria.
- [x] Create a frontend AGENTS.md that explains the current frontend architecture, patterns, and testing strategy.
- [x] Present the plan to the user for approval before starting implementation.

Testing policy: prioritize valuable tests for expected behavior, important edge cases, and integration boundaries. Aim for 80% coverage when it is sensible, but do not treat the percentage as a release gate or add low-value tests solely to reach it.

Tests and validation for Part 1:
- Documentation review: ensure the plan addresses all ten phases below and explicitly calls out test coverage and success criteria.
- Architecture review: confirm that the frontend AGENTS.md matches the actual structure of the app, including app, components, and lib code.

Success criteria:
- User has reviewed the plan and agrees with the phased approach.
- The frontend AGENTS.md accurately reflects the current codebase and will guide future work.
- No implementation proceeds until this plan is approved.

---

## Part 2: Project scaffolding and local runtime baseline

Goal: stand up the containerized application foundation, create the FastAPI backend, and validate that a basic local app and API are running.

Checklist:
- [x] Define the Dockerfile and container layout for the app.
- [x] Add required environment configuration for backend/frontend runtime and local secrets.
- [x] Create the FastAPI backend package structure in backend/.
- [x] Add a minimal health endpoint and a sample API route returning a simple payload.
- [x] Add a static HTML/placeholder response at the root path to confirm the app serves successfully.
- [x] Create start/stop scripts for Mac, PC, and Linux under scripts/.
- [x] Verify the app starts locally and the health/API endpoints respond successfully.

Tests:
- Backend smoke test: ensure the app boots without errors.
- API smoke test: verify /health or a similar endpoint returns a valid JSON response.
- Static serving smoke test: confirm the container/runner serves a page at /.

Success criteria:
- [x] The app runs locally via the provided scripts.
- [x] A simple backend route works and the frontend root responds with an HTML page.
- [x] Docker and backend scaffolding are ready for the actual MVP features.

---

## Part 3: Frontend integration and static serving

Goal: integrate the existing Next.js frontend into the production app and ensure the Kanban board displays properly at /.

Checklist:
- [x] Confirm the Next.js app is buildable for production in the project layout.
- [x] Update the app so the frontend is served by the Python backend at /.
- [x] Ensure the demo Kanban board is presented at the root route without requiring backend data.
- [x] Preserve current design tokens and layout patterns from the existing frontend demo.
- [x] Add unit tests for the board rendering, card list, and drag/move logic.
- [x] Add integration tests that validate page render and core board interactions in a browser.

Tests:
- Unit tests for board state logic, card movement, and creation/deletion flows; coverage is reported to identify important untested behavior.
- Integration tests for initial board rendering and basic interaction pass in Playwright; FastAPI route tests verify the exported page and stylesheet.
- Production build test: `next build` passes without errors and emits the static export.
- Docker image builds and the running container serves the page, assets, health route, and sample API route successfully.

Success criteria:
- [x] The app renders the Kanban board correctly at /.
- [x] Unit tests cover the board logic and pass reliably.
- [x] Integration tests confirm the page loads and core interactions work.
- [x] Coverage is reviewed as a signal; tests prioritize meaningful behavior rather than enforcing a percentage.

---

## Part 4: Hardcoded sign-in flow and logout

Goal: gate access to the board behind a simple dummy auth flow using the required credentials.

Checklist:
- [x] Add a login screen shown before the board when the user is not authenticated.
- [x] Accept the hardcoded credentials user / password only.
- [x] Fail closed for wrong credentials with clear UI feedback.
- [x] Persist the signed-in state for the current session only.
- [x] Add a logout action that clears the session and returns to the login screen.
- [x] Ensure the login and logout flow is protected by tests.

Tests:
- Component tests covering unauthenticated gating, valid and invalid credentials, session restoration in the same tab, and logout.
- Browser integration tests covering failed sign-in, successful sign-in, and logout.

Success criteria:
- [x] Unauthenticated users see the sign-in screen instead of the Kanban board.
- [x] Authenticated users can view and use the board.
- [x] The login experience matches the MVP constraints and simple UX.
- [x] Sign-in survives a reload in the same tab and logout clears the session.
- [x] Board changes survive logout and sign-in again within the same tab session.
- Coverage is reviewed, but the behavior tests above are the acceptance criteria; do not add tests solely to meet a percentage.

Security note: this phase is a frontend-only demo gate using hardcoded credentials. It is not authentication or access control suitable for production; backend enforcement is outside this phase.

---

## Part 5: Database schema design and approval

Goal: define the persistence model for Kanban data and confirm the approach before implementing backend storage.

Checklist:
- [x] Define the board, column, and card API contract in a JSON Schema; propose corresponding user and board persistence tables.
- [x] Document how multiple users will be supported in the future while limiting MVP to one board per user.
- [x] Decide how the database will represent ordering for columns and cards.
- [x] Write the schema documentation in docs/.
- [x] Get explicit user sign-off on the schema before backend implementation begins.

Tests:
- Validate that the JSON Schema file parses and declares the board, column, and card structures used by the frontend.
- Review the proposed constraints for one board per user, foreign-key consistency, and ordered cards.

Success criteria:
- [x] The database design is documented and approved by the user.
- [x] The schema is stored in docs/ and can be implemented directly in SQLite.
- [x] Backend implementation proceeded against the approved data model.

---

## Part 6: Backend API and SQLite persistence

Goal: add a FastAPI backend that can read and write board state for a user and create the database if it does not already exist.

Checklist:
- [x] Create SQLite database initialization and migration/bootstrap setup.
- [x] Define user and board models keyed to the approved schema.
- [x] Add API routes for loading the board, updating columns, adding cards, deleting cards, and moving cards.
- [x] Ensure the backend supports the MVP single-board-per-user model while being structured for multi-user extension.
- [x] Add backend unit tests for each route and state mutation.
- [x] Add integration tests for end-to-end API flows using a temporary test database.

Tests:
- Unit tests for validation and database helper logic.
- API tests for create/read/update/delete operations.
- Test database schema creation and startup behavior.

Success criteria:
- [x] The backend can load and update the Kanban for the seeded MVP user.
- [x] The database is automatically created if absent.
- [x] API routes are covered by tests for meaningful success and failure behavior.
- Coverage is reviewed as a signal; API tests cover meaningful happy paths and error cases without a mandatory percentage gate.

---

## Part 7: Frontend + backend integration for persistent Kanban state

Goal: replace local-only demo state with real backend-backed board data and ensure frontend behavior stays consistent across sessions.

Checklist:
- [x] Connect the frontend to backend API endpoints for board loading and updates.
- [x] Replace local board state with persisted data fetched from the backend.
- [x] Ensure drag-and-drop updates are synchronized to the backend, including target ordering.
- [x] Ensure add-card, delete-card, and rename-column operations persist correctly.
- [x] Add UI and API integration for editing an existing card's title/details and persisting the edit.
- [x] Handle loading, retry, save-progress, and error states.
- [x] Perform integration testing for the full user flow.

Implementation decisions:
- SQLite is the source of truth for board data. The frontend keeps the loaded `BoardData` in an external store; it does not use browser storage as a board cache.
- The MVP frontend calls the fixed `/api/users/user/board` path. The sign-in remains a frontend-only demo gate; the backend routes are not authenticated.
- Each successful mutation returns the complete board. The frontend serializes mutations and replaces its board state with each response rather than applying optimistic updates.
- Column/card ordering uses integer positions in SQLite. Dragging over a card inserts at that card's position; dropping on a column appends.
- Column title edits are submitted on blur after trimming whitespace; blank titles are not submitted.
- `PM_DATABASE_PATH` selects the SQLite file. In Docker, mount a persistent volume at `/app/data` to retain data across container replacement.
- Playwright tests use a stateful API mock for deterministic UI journeys. Cross-layer behavior is additionally checked against the real SQLite API in the Docker-served app.

Tests:
- Frontend unit tests cover API request paths, methods, payloads, response validation, and store error handling.
- Playwright tests exercise sign-in, board rendering, card creation/editing/deletion/movement, column renaming, and persistence through reload/logout/sign-in using a stateful API mock.
- Backend API tests cover SQLite persistence, card edits, and ordered moves; the built Docker app was also exercised live in a browser against its actual SQLite API.

Success criteria:
- [x] Supported board operations are persistent across refreshes and API interactions.
- [x] The frontend and backend remain in sync.
- [x] Test suite covers the main state transitions and failure modes.
- Tests prioritize critical behavior and failure modes; 80% is an aspirational target when sensible, not a release gate.

---

## Part 8: OpenRouter AI connectivity

Goal: verify that the project can make outbound LLM calls through OpenRouter.

Checklist:
- [x] Configure the backend to read the OpenRouter API key from the project environment.
- [x] Use the approved model openai/gpt-oss-120b.
- [x] Add a minimal connectivity endpoint and opt-in integration test using a simple prompt such as "2 + 2".
- [x] Validate the response structure and add mocked tests for valid and invalid provider responses.
- [x] Document failure modes for invalid keys, network issues, timeouts, malformed responses, and provider errors.

Implementation decisions:
- `POST /api/ai/connectivity` submits a fixed `2 + 2` prompt and returns the selected model and non-empty response.
- The backend loads `OPENROUTER_API_KEY` from the repository-root `.env` when present; an existing process environment value takes precedence.
- Provider requests use a 30-second timeout. Missing configuration returns 503; provider/network/timeout/response failures return 502 without exposing the key.
- Fast tests mock HTTP responses. A live provider test is available by setting `RUN_OPENROUTER_INTEGRATION=1`; it has not been run in this workspace because no root `.env` file or process API key is configured.

Tests:
- Unit tests for environment config and request construction.
- Mocked API tests cover request construction, response validation, missing/invalid API keys, and network failures.
- An opt-in integration test sends the prompt to OpenRouter and validates the returned model and response.

Success criteria:
- [ ] The backend makes a successful live AI request with a known-good configuration (requires a configured API key).
- [x] The mocked request contract and response parsing are verified before any Kanban AI logic is built.
- [ ] A live model response is validated; missing API-key configuration leaves this pending.
- [x] The backend handles missing credentials, provider/network failures, timeouts, and malformed responses cleanly.

---

## Part 9: AI board-aware structured outputs

Goal: give the AI access to the Kanban JSON, user message, and conversation context so it can respond with structured output and optional board updates.

Checklist:
- [x] Define the AI request payload structure: user question and optional prior user/assistant messages; the backend injects the current SQLite board.
- [x] Implement strict structured output parsing for the assistant reply and optional Kanban mutations.
- [x] Support plain answers without changing the board.
- [x] Support card creation/updates/moves and column renames.
- [x] Validate the response schema and apply mutations atomically; invalid or partial output leaves the board unchanged.
- [x] Add backend tests for request construction, response parsing, board context, mutations, and failure handling.

Implementation decisions:
- `POST /api/users/{user_id}/board/chat` accepts `{"question": "...", "history": [{"role": "user|assistant", "content": "..."}]}`. History is limited to 20 messages; each message and the question are limited to 4,000 characters.
- The backend fetches the board from SQLite rather than accepting client-supplied board state, and submits it in the system context with conversation history and the latest question.
- OpenRouter is asked for a JSON object containing a non-empty `reply` and optional `actions`. Supported actions are `create_card`, `update_card`, `move_card`, and `rename_column`; delete is intentionally not included.
- Successful responses include the assistant reply, the complete current board, and a `changed` flag. Mutations run in one transaction; invalid references, positions, or malformed model output are rejected without partial updates.
- Backend tests mock OpenRouter. A live model response remains subject to Part 8's configured-key integration check.

Tests:
- Tests cover prompt construction with board/history, JSON-mode request format, text-only responses, each supported mutation type, invalid client and model payloads, unknown board IDs, and transactional rollback.
- Tests validate read-only and mutation responses against a temporary SQLite database while mocking external model calls.

Success criteria:
- [x] The backend constructs a request using board context, question, and conversation history.
- [x] The backend parses responses that include optional Kanban changes.
- [x] Invalid AI output is rejected without corrupting board state.
- AI tests prioritize structured-output behavior, error cases, and state integrity; 80% is aspirational when sensible, not a release gate.

---

## Part 10: AI chat sidebar and automatic UI refresh

Goal: add the final user-facing AI chat experience and ensure the UI refreshes automatically when the LLM modifies the board.

Checklist:
- [ ] Add a sidebar chat widget to the main board UI.
- [ ] Allow the user to send a prompt and receive an AI response in context.
- [ ] Support optional board updates returned by the AI.
- [ ] Automatically refresh the board when AI updates are accepted.
- [ ] Ensure the chat history is preserved and displayed correctly.
- [ ] Add UI tests for chat flows and board refresh behavior.

Tests:
- Frontend unit tests for chat state and UI rendering.
- Integration tests covering AI request, response, and board refresh.
- End-to-end tests verifying that the board updates after an AI mutation.

Success criteria:
- Users can chat with the AI from the sidebar and ask for board changes.
- If the AI updates the board, the UI refreshes automatically without manual reload.
- The overall experience is polished, functional, and tested.
- Final test pass includes both frontend and backend suites with no critical regressions.

---

## Definition of done for the project

- The app supports sign-in with the required MVP credentials.
- The user sees a Kanban board with editable columns and cards, and draggable cards.
- Board state is persisted in SQLite and maintained across requests.
- The backend exposes valid API routes for board operations.
- OpenRouter connectivity is working with the configured model.
- The AI can use board context and structured output to answer questions and optionally modify the board.
- The web UI includes an AI sidebar that reacts to board changes automatically.
- All key modules have valuable unit and integration coverage for important behavior and failure modes; coverage percentages are reported and considered, not used as a mandatory release gate.
- All tests pass before the project is considered complete.

## Approval gate

This plan must be reviewed and approved by the user before implementation begins. Once approved, the agent proceeds to Part 2 scaffolding and runtime validation. The Part 5 database proposal also requires explicit user approval before Part 6 backend persistence work begins.
