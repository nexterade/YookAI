# YookAI v0.1.0 — Full Source Audit & Refactor Report

## Scope

Audited the complete source tree, including:

- Python application/API/server/session/provider/storage code
- HTML/Jinja templates
- CSS
- browser JavaScript
- configuration
- documentation
- existing automated tests

Method followed:

1. Finding
2. Deep inspection / dependency tracing
3. Consolidated findings
4. Refactor/fix at the responsible layer
5. Regression and integration testing
6. Package/zip validation

The goal was to fix root causes rather than stack repeated UI/API patches.

## Findings fixed

### Critical / high impact

1. **Sidebar state had no reliable close/collapse path**
   - Added explicit sidebar collapse control.
   - Header toggle now works on desktop and compact layouts.
   - Mobile backdrop remains a close path.
   - Desktop collapsed state is persisted.
   - Existing `sidebar_default` behavior is respected.

2. **Session switching could race with an active stream**
   - Loading another conversation now stops the active generation before replacing application state.
   - Prevents stream callbacks from writing into the newly selected conversation.

3. **Edit/retry could leave the persisted session stale**
   - Truncation caused by edit/retry is now persisted before the replacement request.
   - Prevents old messages from returning after reload.

4. **No durable memory implementation**
   - Added `core/memory.py`.
   - Memory is local and persistent.
   - `default` mode uses one shared global memory store.
   - `project-only` mode isolates memory by project ID.
   - Relevant prior messages are retrieved and injected as contextual recall.
   - Current conversation remains the authoritative full transcript.

5. **No attachment pipeline**
   - Added secure local attachment storage.
   - Added multipart upload API.
   - Added composer upload UI and attachment chips.
   - 20 MB/file limit.
   - Generated attachment IDs and sanitized filenames.
   - Images are converted to multimodal data URLs.
   - Supported text/code formats are extracted and sent as text.
   - Unsupported binary formats are stored without falsely claiming they were parsed.

6. **No conversation statistics**
   - Added statistics API and UI.
   - Reports:
     - total messages
     - user/assistant messages
     - total/user/assistant characters
     - estimated tokens
     - estimated input/output tokens
     - actual provider input/output/total tokens when the provider reports usage
     - conversation duration
     - start/update timestamps
     - attachment count

### Medium / lower impact

7. **Clipboard fallback was broken**
   - The old optional-chaining expression could still attempt `.then()` on `undefined`.
   - Added a robust Clipboard API fallback using a temporary textarea.

8. **Markdown inline code could be reformatted**
   - Inline code spans were exposed to subsequent emphasis/link regexes.
   - Added placeholder protection so code content stays code.

9. **Provider usage chunks were discarded**
   - Added a normalized `usage` SSE event.
   - OpenRouter usage is captured when available through streaming usage metadata.

10. **Attachment multipart parsing initially depended on attachment disposition**
    - Refactored multipart parsing to walk leaf MIME parts and detect the uploaded filename reliably.

11. **Chat options were insufficiently validated**
    - `options` must now be an object rather than allowing malformed values to fall through into a server-side exception.

12. **Stop requests for unknown providers could become HTTP 500**
    - Provider resolution now maps invalid provider names through the normal API error path.

## Root-level refactor

The major additions were placed at the storage/application boundaries instead of embedding everything in frontend state:

```text
core/
  memory.py
  attachments.py

app/
  routes.py
  server.py
  sse.py

providers/
  openrouter.py

templates/
  app.js
  api.js
  markdown.js
  composer.html
  sidebar.html
  header.html
  index.html
  style.css
```

This keeps:

- storage concerns in `core`
- HTTP/multipart concerns in `app.server`
- API orchestration in `app.routes`
- provider-specific behavior in `providers`
- presentation/state behavior in the frontend

## Memory behavior

### Default memory

Shared across chats/projects within the same local YookAI installation.

Storage:

```text
~/.yookai/memory/global.json
```

### Project-only memory

Isolated by:

```text
memory.project_id
```

Storage:

```text
~/.yookai/memory/projects/<project_id>.json
```

The current implementation uses lightweight lexical retrieval rather than an external embedding service, keeping memory fully local and dependency-light.

## Attachment behavior

Storage:

```text
~/.yookai/attachments/
```

The browser never needs to know the physical filesystem path.

Supported directly in provider requests:

- images
- plain text
- Markdown
- CSV
- JSON
- XML
- HTML
- CSS
- JavaScript
- Python
- logs and similar text formats

PDF/binary files can be stored and attached, but are not currently parsed into text without a dedicated document-extraction dependency.

## Testing

Final automated test result:

```text
92 passed
```

Additional validation:

- Python bytecode compilation: passed
- JavaScript syntax checks with Node:
  - `templates/app.js`: passed
  - `templates/api.js`: passed
  - `templates/markdown.js`: passed
- Jinja template rendering: passed
- DOM ID/reference audit: passed
- Multipart attachment integration test: passed
- Server integration tests: passed
- Memory isolation tests: passed
- Attachment storage tests: passed
- Conversation statistics tests: passed

## Residual limitations

These are feature-scope limitations rather than unresolved regressions:

1. Token estimation is heuristic when the provider does not return usage.
2. Full historical memory is persisted locally, but retrieval is relevance-based to avoid blindly injecting an unbounded transcript into the model context window.
3. PDF/document parsing beyond supported text formats is not included yet.
4. No real upstream OpenRouter request was made during the audit because that would require a live credential and external network access.
5. No browser automation/E2E visual test suite is included; frontend behavior was validated through JavaScript syntax, template rendering, static DOM checks, and the existing frontend contract tests.

## Result

The project now has a coherent base for the requested features instead of accumulating independent patches around the original implementation.

The regression suite increased from **83 tests to 92 tests**.
