# Sessions

## Schema

A session is a JSON object containing at least:

```json
{
  "id": "2026-10-02-001",
  "title": "New Chat",
  "provider": "openrouter",
  "model": "deepseek/deepseek-r1",
  "created_at": "2026-10-02T00:00:00+00:00",
  "updated_at": "2026-10-02T00:00:00+00:00",
  "messages": [],
  "metadata": {}
}
```

## Location and naming

Sessions live at `~/.yookai/sessions/`. The file name is `<id>.json`. IDs follow `YYYY-MM-DD-NNN`. Creation is serialized within the server process to avoid duplicate IDs under concurrent requests, and writes use unique temporary files before atomic replacement.

## API

- `GET /api/session/list` — compact metadata list.
- `POST /api/session/save` — create or update a session.
- `GET /api/session/{id}` — load a session.
- `DELETE /api/session/{id}` — delete a session.

## Migration

YookAI v0.1.0 retains the JSON session shape used by the preceding batches. Older session files are loaded as dictionaries and missing optional fields receive defaults during save. Invalid IDs are rejected rather than used as filesystem paths.
