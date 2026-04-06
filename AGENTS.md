# AGENTS.md

## Project

GazeVibe: eye-tracking AI programming assistant. Vue 3 + Vite frontend, Python Flask + DeepSeek API backend. No TypeScript — plain JS with ES modules. No test framework, no linter configured.

## Run

```bash
# Frontend
cd frontend && bun install && bun run dev   # http://localhost:5173
bun run build                                 # production build

# Backend (uses existing venv at backend/.venv)
backend/.venv/bin/python backend/app.py       # http://localhost:8000
# Or: cd backend && bash run.sh               # creates venv if needed

# Health check
curl http://localhost:8000/api/health
```

**Backend has no `pip`** — use the venv directly or `uv`. `pip install -r requirements.txt` will fail.

**API key**: `DEEPSEEK_API_KEY` in `backend/.env` (not in git).

## Architecture

- Vite dev server proxies `/api` → `http://localhost:8000` (`vite.config.js`)
- `/api/ask` makes **two separate** DeepSeek calls — one "detailed tutor" system prompt, one "concise assistant" system prompt — returns `{answerA, answerB}`
- File System Access API (`window.showDirectoryPicker`, `readwrite` mode) — Chrome 86+ only
- Files indexed in memory via `fileIndexer.js`, not persisted

### Code Apply Workflow

1. `codeParser.js` parses code blocks from AI answers, `extractFilePath` matches them to project files
2. Only blocks with a matched file path get a "暂存修改" button; blocks without a path show code preview only
3. Click "暂存修改" → DiffPreview modal → "应用修改" to stage → button becomes red "已暂存 (取消)"
4. Click "选择此答案" → writes all staged files to disk via `fileIndexer.writeFile()`

**Deduplication**: `allResolvedBlocks` in `AnswerPanel.vue` deduplicates across both panels by file path. If both answers target the same file, only the first panel's block is kept.

**Content filtering**: `isFileApplicable()` rejects bash/shell commands, compiler output (`Compiling`, `Finished`, `Running`), error traces, and blocks under 3 lines.

**File path extraction priority** (`extractFilePath` in `codeParser.js`):
1. Explicit labels in text before code block (e.g., "file: src/main.rs")
2. Path-like patterns (e.g., `src/foo.js`)
3. Fuzzy filename matching
4. First line of code block content (if it looks like a filename)
5. Language-to-extension fallback against project files

### Eye Tracking

WebGazer initialized once, then `resume()`/`pause()` per session. Camera preview hidden via DOM manipulation. Tracking pauses when DiffPreview is open — eye data is silently discarded.

### State

- `fileChanges` Map (key: filePath, value: {content}) — shared between A and B panels in AnswerPanel
- `file._originalContent` — set on stage, used for rollback on unstage, deleted after disk write
- `commitAll()` only clears UI state; actual writes happen in `App.vue handleChoice()`

## Code Style

### Frontend (Vue 3)

- `<script setup>` only (Composition API), no Options API
- Components: PascalCase, CSS classes: kebab-case
- `<style scoped>`, CSS variables from `src/styles/everforest.css`
- No comments unless asked, no emojis in code/commits

### Backend (Python Flask)

- PEP 8, 4-space indent, double quotes
- Routes: `@app.route("/api/...", methods=[...])`
- Error responses: `jsonify({...})` with status codes (400/500)
- `success: true/false` field in action responses

## Theme

Everforest Dark Medium. Font sizes are **1.5x scaled** — `--font-xs` is 18px (not the default 12px). All colors as CSS variables in `src/styles/everforest.css`.
