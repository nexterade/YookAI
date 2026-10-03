# YookAI

**One interface for many AI.**

[![Version](https://img.shields.io/badge/version-0.3.28-blue.svg)](#release-notes) [![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](#requirements) [![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

YookAI is a local multi-model AI chat workspace built with Python, a standard-library HTTP server, Server-Sent Events, Jinja2, and vanilla HTML/CSS/JavaScript. Provider adapters currently cover OpenRouter, OpenAI, Anthropic, Google Gemini, and Ollama's HTTP API.

> **Release status:** v0.3.28 is a public testing build. Review the known limitations and release checklist before using it beyond a local development environment.

## Features

- Streaming chat with multiple provider adapters and model selection.
- Persistent local sessions, memory, attachments, and conversation statistics.
- Responsive browser UI with dark/light themes, keyboard shortcuts, and accessible interaction states.
- Local tools including calculator and workspace-scoped filesystem operations.
- Optional shell tool, disabled by default, with command allowlisting, workspace limits, timeout, and confirmation.
- CLI diagnostics, configuration, storage management, and Semut file/folder utilities integrated as a separately namespaced suite.
- Isolated capability foundations for agents, projects, context planning, MCP helpers, research fetch, and automation metadata. These foundations are not all exposed as complete end-to-end UI features; see [v0.3.0 capability boundaries](docs/V0.3.0_FINAL.md).

## Requirements

- Python 3.10 or newer.
- Dependencies listed in `requirements.txt`.
- Node.js is optional and only needed for the documented JavaScript syntax checks.

## Installation

Download and extract the source archive from the GitHub repository, then run from the extracted project directory:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If installing from a Git clone, use the repository's actual clone URL shown on its GitHub page, then enter the cloned directory before running the commands above.

## Quick start

```bash
python server.py --no-open
```

Open `http://127.0.0.1:8000/` in your browser. On first start, YookAI creates its runtime layout under `~/.yookai/` using `config.example.json`. Configure a provider API key in the Settings UI or local settings file.

## Security notes

YookAI is designed for local use and binds to `127.0.0.1` by default. Binding to a non-loopback address is rejected unless `server.api_key` is configured. The browser UI does not currently provide an interactive server-key prompt, so keyed non-loopback access is intended for authenticated custom API clients rather than the built-in browser UI. The built-in server is not a hardened multi-user production gateway; use localhost for the browser UI and an appropriately secured reverse proxy for any externally reachable deployment. Keep `~/.yookai/` private and never commit API keys, sessions, or memory data. Optional shell execution is disabled by default; enabling it grants local command execution within the tool's configured restrictions and should be done only when understood.

## Configuration and runtime data

Runtime data is stored outside the repository under `~/.yookai/`, including settings, provider configuration, sessions, prompts, cache, memory, and attachments. API credentials are masked in the configuration API response. Back up important runtime data before editing or clearing it.

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

## Architecture and guides

- [Architecture](docs/ARCHITECTURE.md)
- [Provider setup](docs/PROVIDERS.md)
- [Sessions](docs/SESSIONS.md)
- [Roadmap](docs/ROADMAP.md)
- [Contributing](docs/CONTRIBUTING.md)
- [Semut integration, ownership, and licensing notes](docs/SEMUT_MISC_INTEGRATION.md)
- [Release checklist](docs/RELEASE_CHECKLIST.md)

## Testing

```bash
python -m compileall -q .
node --check templates/app.js
node --check templates/api.js
node --check templates/markdown.js
python -m pytest -q
```

## License

YookAI's project license is MIT; see [LICENSE](LICENSE). Third-party and vendored components may have separate licensing terms. The bundled Semut snapshot is maintained by @nexterade and has separate snapshot metadata; document its applicable license and retain any third-party notices before redistributing the combined source archive.

## Release notes

See [docs/CHANGELOG.md](docs/CHANGELOG.md) for v0.3.28 and previous changes.
