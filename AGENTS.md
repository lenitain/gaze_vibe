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
4. Click "选择此答案" → writes staged files **from that panel only** to disk via `fileIndexer.writeFile()`

**Per-panel commits**: Left button commits `fileChangesA`, right button commits `fileChangesB`. Each file stores `_stagedBy` ('A' or 'B') to track which panel staged it. `handleChoice(side)` only writes files where `file._stagedBy === side`.

**Panel isolation**: `codeBlocksA` shows only source A blocks, `codeBlocksB` shows only source B blocks. Each panel has independent file path deduplication (`usedPathsMap` — one Set per source), so both panels can suggest different changes to the same file.

**Content filtering**: `isFileApplicable()` rejects bash/shell commands, compiler output, error traces, and blocks under 2 lines.

**File path extraction** (`extractFilePath` in `codeParser.js`):
1. Explicit labels in text before code block (e.g., "file: src/main.rs")
2. Path-like patterns (e.g., `src/foo.js`)
3. Fuzzy filename matching
4. First line of code block content (if it looks like a filename)
5. Language-to-extension fallback against project files

### Choice & Preference Submit

`handleChoice(side)` fires API call and file writes **in parallel** — only `await apiPromise` blocks, file writes run in background. Users see "偏好已保存" immediately without waiting for file I/O.

### Question Display

`handleSubmit` stores the question in `currentQuestion`, displays it in a user bubble with a loading spinner. `answerPanelRef.resetChoice()` is called at the start of each submission to restore both panels.

### Eye Tracking

WebGazer initialized once, then `resume()`/`pause()` per session. Camera preview hidden via DOM manipulation. Tracking indicator shows current region (详细解答/简洁解答) with side-specific color (blue/green).

During DiffPreview: eye data is attributed to the side that opened the diff (`diffOpenSide`), not discarded.

### State

- `fileChangesA` / `fileChangesB` — separate Maps per panel, key: filePath, value: {content}
- `file._originalContent` — set on stage, used for rollback on unstage
- `file._stagedBy` — 'A' or 'B', determines which panel's commit writes this file
- `block._panel` — forces a block's actions to target a specific panel's state
- `commitAll(side)` only clears UI state; actual writes happen in `App.vue handleChoice()`
- `resetChoice()` — resets `selectedSide`, `choiceDisabled`, and both `fileChanges` Maps; called on each new submission

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
