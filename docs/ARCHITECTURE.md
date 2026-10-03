# YookAI Architecture

## Four layers

```text
┌──────────────────────────────────────────────┐
│ UI: Jinja2 + HTML/CSS + vanilla JavaScript │
│ app.js / api.js / markdown.js               │
└──────────────────────┬───────────────────────┘
                       │ HTTP + SSE
┌──────────────────────▼───────────────────────┐
│ API: http.server + APIHandler               │
│ routes.py / server.py / sse.py              │
└──────────────────────┬───────────────────────┘
                       │ BaseProvider
┌──────────────────────▼───────────────────────┐
│ Provider: OpenRouter adapter                │
│ registry.py / openrouter.py                 │
└──────────────────────┬───────────────────────┘
                       │ JSON/files + HTTPS
┌──────────────────────▼───────────────────────┐
│ Storage: ~/.yookai/                         │
│ config / sessions / prompts / cache         │
│ memory / attachments                        │
└──────────────────────────────────────────────┘
```

## UI layer

`templates/_shared/base.html` provides Jinja2 inheritance and the anti-FOUC theme script. `index.html` composes partials and inlines CSS/JS with Jinja2 includes. No frontend framework or CDN is required.

## API layer

`app/server.py` owns `ThreadingHTTPServer` and translates HTTP methods/paths into `APIHandler` calls. `app/routes.py` contains endpoint logic independent of the HTTP transport. `app/sse.py` formats normalized events as `data: <json>\n\n`.

## Provider layer

`providers/base.py` defines the provider contract. `OpenRouterProvider` implements model listing, streaming chat, stop signaling, one-hour model caching, and upstream HTTP error classes for 401/402/429.

## Storage layer

`core/paths.py` is the single source of canonical runtime paths. `SessionManager` stores one JSON document per session. `core/config.py` validates and persists configuration.

## Chat data flow

1. Browser sends `POST /api/chat` with provider, model, and messages.
2. `APIHandler` validates input and obtains a provider from the registry.
3. OpenRouter streams upstream SSE data.
4. Provider normalizes deltas to reasoning/content/done/error chunks.
5. HTTP transport serializes each chunk as an SSE event.
6. `api.js` parses the stream incrementally; `app.js` updates the message and thinking block.
7. Completed conversations are persisted through `/api/session/save`.

## Session flow

The sidebar requests `/api/session/list`, then `/api/session/{id}` for a selected conversation. Saving uses `/api/session/save`; deletion uses `DELETE /api/session/{id}`.

## Config flow

The Settings UI reads `/api/config`. API keys are masked in the response. When a masked key is submitted back, the server preserves the existing credential instead of overwriting it with the mask.

## File structure

```text
app/        HTTP/API/session/SSE application code
core/       paths, config, logging
providers/  provider abstraction and OpenRouter adapter
templates/  Jinja2 HTML, CSS, and vanilla JS
tests/      unit and static-analysis tests
docs/       architecture, provider, session, roadmap, contribution docs
server.py   CLI entry point
```

## Security and production safeguards

- Local deployments bind to `127.0.0.1` by default; exposing the server externally should be an explicit operator decision.
- API credentials are masked recursively in configuration responses, including an optional server authentication key.
- Default browser/API responses do not enable wildcard CORS.
- Configuration and session writes use atomic replacement to reduce corruption on process interruption.
- Provider instances are refreshed when provider credentials or base URLs change, avoiding stale credentials after Settings changes.

## Design decisions

- Python stdlib HTTP transport keeps deployment lightweight.
- Jinja2 inheritance supports future pages without a frontend framework.
- SSE keeps streaming incremental and browser-native.
- Runtime state lives under `~/.yookai/`, not inside the repository.
- The browser never receives an unmasked API credential.


## Memory architecture

YookAI persists chat messages into a local memory store when sessions are saved. The configured mode controls the retrieval scope:

- `default`: one global local memory store shared across chats/projects on this installation.
- `project-only`: a separate local memory store keyed by `memory.project_id`; records from other project IDs are not retrieved.

The current conversation remains the authoritative full transcript. Before a request is sent, a lightweight lexical retrieval pass adds relevant prior messages as a system-context block. This avoids pretending that a model has unlimited context while still making long-lived recall durable.

## Attachments

Attachments are stored outside the repository under `~/.yookai/attachments/` with generated IDs and sanitized filenames. Images are converted to data URLs for OpenAI-compatible multimodal requests; supported text/code formats are decoded and included as text. Unsupported binary formats remain stored and are identified to the model without pretending they were parsed.

## Conversation statistics

Session statistics are derived from persisted message metadata. The UI reports message counts, character counts, estimated tokens, actual provider token usage when supplied, duration, timestamps, and attachment counts.
