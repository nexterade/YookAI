# YookAI

**One interface for many AI.**

[![Version](https://img.shields.io/badge/version-0.3.8-blue.svg)](#) [![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](#) [![License](https://img.shields.io/badge/license-MIT-green.svg)](#license)

YookAI is a standalone multi-model AI chat client using Python's standard-library HTTP server, Server-Sent Events, vanilla HTML/CSS/JavaScript, Jinja2 templates, with a provider abstraction supporting OpenRouter, OpenAI, Anthropic, Google Gemini, and Ollama HTTP API adapter.

> Screenshot: placeholder — replace with a release screenshot.

## Features in v0.3.0-final

- v0.3.8: fresh browser visits and server restarts open the Start Page; refreshing the same tab on the same server preserves its active chat. Chat history remains available in the sidebar.

- Local tool engine with safe calculator and workspace-scoped filesystem tools.
- Optional shell tool with allowlist, no shell interpreter, workspace confinement, timeout, and one-time confirmation tokens.
- Tools API and Tools UI for explicit local execution.
- Bounded agent loop, project-scoped workspace, context budgeting/compaction, task ledger, disabled-by-default schedule metadata, MCP JSON-RPC helpers, and bounded public-HTTPS fetch utility.
- New capability modules are isolated and opt-in; provider-specific autonomous tool-call transport, browser search provider, background worker lifecycle, and full MCP process transport remain integration points rather than silently enabled behavior.

## Features in v0.3.0-alpha2

- Incremental domain architecture introduced without breaking the v0.2.4 API/provider contracts.
- Stable chat, session, model-profile, provider-health, and local-tool boundaries.
- New `tools/doctor.py` diagnostic command.
- Dedicated `static/` asset tree for the next UI/icon refactor.

## Features in v0.2.4

- Multi-provider streaming chat: OpenRouter, OpenAI, Anthropic, Google Gemini, and Ollama API.
- SSE API with reasoning/content/done/error chunks.
- Persistent JSON sessions under `~/.yookai/sessions/`.
- Configuration under `~/.yookai/config/`, with API-key masking in `GET /api/config`.
- Responsive DeepSeek × Qwen-inspired UI with dark/light theme.
- Offline-first Markdown renderer with HTML/link sanitization.
- Model selector with one-hour cache, search, recommended/free/all grouping, keyboard navigation, and persisted selection.
- Thinking/reasoning block with streaming expansion, elapsed timer, Markdown rendering, and manual-collapse persistence.
- Accessibility focus states, reduced-motion support, keyboard shortcuts, and mobile touch targets.
- 121 automated tests covering backend, provider adapters, storage, frontend contracts, memory, attachments, SSE, and server integration.
- Local durable memory with Default and Project-only modes.
- Conversation statistics with estimated/actual token usage, message/character counts, duration, timestamps, and attachment counts.
- Local attachment upload (20 MB/file) with image and text/code extraction for provider requests.
- Collapsible sidebar on desktop/mobile with persistent desktop collapse state.
- Provider-aware model selector and per-model session profiles.
- Session snapshots retain model settings used for each conversation.
- ZIP-aware attachments with animated upload progress.

## Installation

```bash
git clone <repository-url>
cd yookai
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

## Quick start

```bash
python3 server.py --no-open
```

Open `http://localhost:8000/`.

On first start, YookAI creates its runtime layout under `~/.yookai/` from `config.example.json`.

## Configuration

Runtime files are deliberately outside the repository:

```text
~/.yookai/
├── config/
│   ├── settings.json
│   └── providers.json
├── sessions/
├── prompts/
└── cache/
```

Set the OpenRouter API key in `~/.yookai/config/settings.json` or through the Settings UI. Credentials are never rendered in clear text by `GET /api/config`.

## Keyboard shortcuts

| Shortcut | Action |
|---|---|
| Enter | Send message |
| Shift+Enter | New line |
| Ctrl/Cmd+K | New chat |
| Ctrl/Cmd+/ | Toggle sidebar |
| Escape | Close dropdown/modal |
| Arrow Up/Down | Navigate model selector |
| Enter in model selector | Select model |

## Architecture

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and [`docs/V0.3.0_ARCHITECTURE.md`](docs/V0.3.0_ARCHITECTURE.md).

## Roadmap

See [`docs/ROADMAP.md`](docs/ROADMAP.md) for planned v0.2–v1.0 work.

## Contributing

See [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md).

## License

MIT. See [LICENSE](LICENSE).

## v0.2.0

v0.2.0 expands YookAI into a fuller local AI workspace:

- PDF/DOCX/XLSX/XLSM/text attachment extraction.
- Deterministic local semantic memory retrieval with Default and Project-only isolation.
- Memory manager with search/delete/clear.
- Conversation search and JSON export/import.
- Attachment lifecycle APIs and orphan cleanup.
- Provider model capability metadata and persisted usage/cost accounting.
- Drag-and-drop attachments and expanded conversation statistics.
- Responsive ChatGPT-inspired UI with collapsible sidebar, centered model selector, bottom composer, dark/light themes, keyboard shortcuts, and mobile behavior.

The visual system intentionally follows familiar ChatGPT interaction patterns while retaining YookAI branding and localhost-specific controls.

## v0.3.0-rc1

YookAI v0.3.0-rc1 establishes the local AI tool layer. Tools run on localhost under explicit permission boundaries rather than directly inside provider adapters.

## v0.2.4

YookAI v0.2.4 turns the provider layer into a real multi-provider local workspace. Provider/model selection is now first-class, model settings can be saved per provider+model, and each conversation records the configuration used for reproducibility. Ollama connects to a separately running Ollama server through its HTTP API.


## v0.3.0-final capability modules

The release adds modular foundations under `core/agents`, `core/projects`, `core/context`, `core/mcp`, `core/research`, and `core/automation`. The agent loop is bounded and delegates execution/approval to the host application. Project files are confined to each project's `files/` directory. Context planning estimates tokens conservatively and retains recent complete messages. Task and schedule stores are local JSON ledgers; schedules are disabled until an application worker explicitly enables and executes them. MCP helpers implement JSON-RPC message validation; they do not launch arbitrary MCP processes. Research fetch is HTTPS-only, size-bounded, and blocks local/non-public targets; search and citation generation require a configured upstream integration.

Run tests with `pytest -q`. See `docs/V0.3.0_FINAL.md` for scope and operational boundaries.
