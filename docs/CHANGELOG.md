## v0.3.8
- Open Start Page on fresh browser visits and after YookAI server restarts instead of auto-opening the most recent chat.
- Preserve the active conversation across a browser refresh in the same tab and same server instance.
- Keep previous conversations in the sidebar for explicit user-selected resume; New Chat clears the tab active-session pointer only.

## v0.3.7
- Fixed Ollama API CLI setup: default server URL is shown and persisted even when left unchanged.
- Ollama model selection now loads models from the configured server, with manual fallback when unreachable.
- Switching providers preserves each provider model separately and initializes Ollama to `llama3.2` instead of reusing a cloud model.
- Clarified Ollama API status and removed duplicate full guide from the credentials screen.

## v0.3.6
- Clarified Ollama as a remote/self-hosted HTTP API provider rather than implying native offline support on Android/Termux.
- Updated CLI and web labels/setup guidance to configure a reachable Ollama server URL.

## v0.3.5
- Label providers as free-tier, local-free, or paid in the CLI provider menu.
- Put free-tier and local options first; clarify that OpenRouter and Gemini free access has model/usage limits and may include paid choices.

## v0.3.4
- Added provider-specific setup guides in the CLI, including official API-key dashboard links, model selection guidance, base URLs, and Ollama local setup notes.

# Changelog

## v0.3.3
- Replace the static CLI benchmark glyph with a live threaded spinner in interactive terminals.
- Keep benchmark/network work outside the animation thread and cleanly stop the spinner on success or error.
- Print a non-animated status line when output is not a terminal.


## v0.3.2
- Improve CLI startup menu with ANSI color styling and clearer section labels; gracefully degrades when color is unavailable.
- Apply CLI-configured browser theme when the saved CLI theme changes.
- Refresh the browser's selected model when the configured CLI default model changes.
- Ignore SSE comments and metadata lines instead of attempting to parse them as JSON.


## 0.3.0-rc1
- Added local tool engine and registry.
- Added safe calculator and workspace-scoped filesystem tools.
- Added opt-in shell execution with command allowlist, workspace confinement, timeout, and one-time confirmation.
- Added `/api/tools` and `/api/tools/execute`.
- Added Tools UI and security regression tests.

## 0.3.0-beta1

- Added smart latency/capability-aware model/provider routing.
- Added pre-token provider/model fallback.
- Added 60-second in-process model catalog cache.
- Added benchmark result caching for routing.
- Added session schema v2 fields for model configuration and routing metadata.
- Promoted bounded ZIP/document processing to the beta baseline.

## 0.2.4

- Fixed retry/repeat to target the clicked user turn and preserve its attachments.
- Fixed upload UI so 100% means server-confirmed completion; the spinner no longer remains at 100%.
- Added direct OpenAI, Anthropic, Google Gemini, and local Ollama provider adapters.
- Added provider switching in the model selector.
- Added per-provider/model session profiles for temperature, top-p, max tokens, reasoning effort, and system prompt.
- Snapshotted model configuration into each conversation session.
- Fixed stop/cancel routing so it targets the active provider.
- Expanded startup configuration to cover all supported providers.

## 0.2.3

- Added interactive pre-listen configuration menu for `python3 server.py`.
- Added `--no-configure` and `--configure` startup flags.
- Added live TTFT benchmarking for free OpenRouter models with six-hour cache.
- Migrated the legacy DeepSeek R1 hard-coded default to latency-based selection.
- Added real attachment upload progress, spinner, percentage and progress bar.
- Prevented sending while attachment uploads are still active.

## 0.2.2

- Persist new chat sessions before model streaming so History is immediately populated.
- Added bounded ZIP attachment extraction for text/document members.
- Added ZIP file picker support.
- Reduced avoidable SSE buffering with `iter_lines(chunk_size=1)`.
- Added OpenRouter stream timing logs for connect/first-event/total latency.
- Advertise `text/event-stream` to the upstream provider.
- Added regression tests for ZIP processing, History persistence, and streaming latency.

## 0.2.1

- Fixed SSE handler closing the HTTP-owned `wfile`, eliminating post-stream `ValueError: I/O operation on closed file`.
- Added immediate animated thinking spinner/timer.
- Forced UTF-8 provider decoding and added conservative mojibake repair.
- Replaced UI Unicode glyph icons with inline SVG controls.
- Fixed mobile sidebar backdrop selector.

# Changelog

## 0.2.0
- Local document extraction for PDF, DOCX, XLSX/XLSM and text formats.
- Deterministic local semantic memory retrieval and memory manager UI.
- Session export/import API and conversation search.
- Attachment lifecycle listing, deletion and orphan cleanup.
- Provider model capability metadata and usage/cost accounting.
- ChatGPT-inspired responsive visual system and composer/sidebar redesign.
- Drag-and-drop attachments, file previews and expanded statistics.

# Changelog

## [0.1.0] - 2026-10-02

### Added

### Fixed

- Settings changes now invalidate stale provider instances and credentials.
- Initial frontend boot no longer fails completely when the model endpoint is unavailable; sessions and Settings remain usable.
- Chat cancellation/new-chat races are guarded so an old stream cannot mutate a newer conversation.
- Session titles are derived from the first user message when still using `New Chat`.
- Concurrent session creation and writes use safer synchronization/atomic replacement.
- Configuration writes use atomic replacement.
- Configuration responses mask credential-like fields beyond provider API keys.
- Default server binding is now loopback-only and wildcard CORS was removed.
- Added baseline HTTP integration tests and expanded the suite to 81 tests.

- Standalone multi-model AI chat client.
- Provider abstraction (`BaseProvider`).
- OpenRouter provider with streaming, stop, model listing, caching, and upstream error mapping.
- Session manager under `~/.yookai/sessions/`.
- Config loader under `~/.yookai/config/`.
- HTTP server using `http.server` and `ThreadingHTTPServer`.
- SSE streamer and normalized reasoning/content/done/error events.
- 10 API endpoint groups for providers, chat, sessions, and config.
- Vanilla HTML/CSS/JS frontend with Jinja2 inheritance.
- Model selector with search, grouping, keyboard navigation, cache, and persistence.
- Thinking block with auto-expand, timer, Markdown rendering, and auto-collapse.
- Dark/light theme and responsive mobile layout.
- Offline-first Markdown renderer with XSS-safe HTML/link handling.
- Accessibility, reduced-motion, loading, toast, error, and keyboard-interaction polish.
- 83 automated tests.

### Security

- API keys are masked by `GET /api/config`.
- Masked API keys submitted by the UI do not overwrite the real credential.
- Markdown output escapes raw HTML and restricts generated links to HTTPS URLs.
- Runtime paths are canonicalized through `core/paths.py`.

### Documentation

- README.md
- docs/ARCHITECTURE.md
- docs/PROVIDERS.md
- docs/SESSIONS.md
- docs/ROADMAP.md
- docs/CONTRIBUTING.md
- docs/CHANGELOG.md

## [0.5.0] - 2026-10-02

### Added

- Functional model selector and reasoning/thinking block from PR VIII–IX.

## [0.4.0] - 2026-10-02

### Added

- Jinja2 frontend with shared base template.
- Responsive HTML/CSS interface.
- Vanilla JavaScript API client, SSE chat flow, session UI, theme handling, and Markdown renderer.

## [0.3.0] - 2026-10-02

### Added

- SSE formatting and streaming helpers.
- Threaded HTTP transport and API routes.

## [0.2.0] - 2026-10-02

### Added

- Provider abstraction and OpenRouter provider.
- Persistent session manager.

## [0.1.0-pre] - 2026-10-02

### Added

- Initial project skeleton, configuration, paths, and logger.


## Audit/refactor
- Fixed sidebar close/collapse behavior across desktop and compact layouts.
- Prevented session switching from racing with an active stream.
- Persisted edit/retry truncations before resending.
- Added local memory, attachment upload, conversation statistics, and actual provider usage capture.
- Fixed clipboard fallback and Markdown inline-code formatting interactions.
- Added regression and integration coverage.

## v0.3.0-alpha1

- Introduced the incremental v0.3 domain architecture without breaking the v0.2.4 API surface.
- Added domain facades for chat, sessions, attachments, memory and documents.
- Added normalized model descriptors and provider/model-scoped profile helpers.
- Added provider health primitives for future latency-aware routing and fallback.
- Added a local tool registry foundation with confirmation metadata.
- Added `tools/doctor.py` for local runtime diagnostics.
- Added dedicated `static/`, `runtime/`, domain package and test subtrees.

## v0.3.0-alpha2
- Added Provider Registry 2.0 with provider metadata and local/remote classification.
- Added live normalized multi-provider model catalog and capability inference.
- Added provider health probing based on model discovery latency.
- Added provider-native latency benchmark orchestration and best-result selection.
- Added API endpoints for provider specs, live model catalog, health, and benchmarks.

## 0.3.0-rc1
- Added local tool engine and tool registry execution API.
- Added safe calculator and workspace-scoped filesystem tools.
- Added opt-in shell tool with confirmation and command sandbox.
- Added tool security regression tests.

## 0.3.0-final

- Added bounded agent-loop orchestration primitives with approval delegation.
- Added project workspace storage and confined project file operations.
- Added deterministic context budgeting and extractive compaction helpers.
- Added persistent task ledger and disabled-by-default interval schedule metadata.
- Added MCP JSON-RPC protocol helpers and bounded public-HTTPS fetch utility.
- Updated release metadata, documentation, and service-level tests.
- Provider-native tool calling, search/citation adapters, MCP process transport, and managed background workers remain explicit integration work; see `V0.3.0_FINAL.md`.


## v0.3.0 final-fix-006
- Show a clear, non-fabricated note in the Thinking disclosure when a model does not provide reasoning data.
- Allow any late reasoning chunks to replace the unavailable-state note.
- Keep Thinking live through content chunks and finalize it on terminal completion/stream close.
