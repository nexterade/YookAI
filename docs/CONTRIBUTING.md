# Contributing

## Workflow

1. Create a focused branch.
2. Make the smallest change that satisfies the issue/PR.
3. Add or update tests for behavior changes.
4. Update documentation when public behavior changes.
5. Run syntax checks and the full test suite.
6. Open a PR with a concise description and verification output.

## Code style

- Python: standard library patterns, type hints where useful, no `os.getcwd()`; resolve project paths through `core/paths.py`.
- Frontend: vanilla JavaScript, semantic HTML, CSS variables, no framework or CDN.
- Keep API credentials out of browser responses and source control.

## Test requirement

A behavior change must include automated coverage where practical. Release candidates must pass:

```bash
python3 -m compileall -q .
node --check templates/app.js
node --check templates/api.js
node --check templates/markdown.js
python3 -m pytest -q
```

## Commit convention

Use concise imperative subjects, for example:

```text
feat: add provider model cache
test: cover SSE error chunks
docs: update provider guide
fix: preserve masked API key
```

## PR process

Describe the change, affected files, tests run, and any known limitations. Avoid unrelated refactors in feature PRs.
