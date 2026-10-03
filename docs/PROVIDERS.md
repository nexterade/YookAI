# Providers

YookAI uses a common `BaseProvider` interface so the chat UI and session layer do not depend on one vendor.

## Built-in providers

| Provider | Identifier | Credential | Streaming | Local |
|---|---|---|---|---|
| OpenRouter | `openrouter` | API key | SSE | No |
| OpenAI | `openai` | API key | SSE | No |
| Anthropic | `anthropic` | API key | SSE | No |
| Google Gemini | `gemini` | API key | SSE | No |
| Ollama API | `ollama` | None by default (self-hosted server) | NDJSON | No (remote API) |

### OpenRouter

Used for multi-model routing and the latency benchmark. Free-model TTFT probing can select a low-latency default.

### OpenAI

Direct OpenAI-compatible Chat Completions adapter. Model IDs are obtained from `/v1/models`.

### Anthropic

Direct Messages API adapter with text/image normalization and reasoning-event support.

### Google Gemini

Direct Generative Language API adapter with streaming `generateContent` responses and multimodal data-URI normalization.

### Ollama

HTTP API adapter for a separately running Ollama server. It reads available models from `/api/tags` and streams `/api/chat` responses. On Android/Termux, configure the reachable LAN/server URL instead of assuming Ollama runs locally. The API usually has no built-in authentication; keep it on a trusted network or protect it with an authenticated proxy.

## Provider configuration

Provider credentials and base URLs live in `~/.yookai/config/settings.json` and are never exposed in clear text by `GET /api/config`.

The web UI and startup menu can select the active provider. The model selector reloads models when the provider changes.

## Model profiles

`chat.model_profiles` stores settings under `provider:model` keys. Profiles currently support:

- temperature
- top-p
- max tokens
- reasoning effort (`auto`, `low`, `medium`, `high`)
- system prompt

A session stores a `model_config` snapshot so historical conversations retain the configuration used when they were generated.
