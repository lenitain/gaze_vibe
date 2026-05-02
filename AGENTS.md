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

### Code Block Display

1. `codeParser.js` parses code blocks from AI answers, `extractFilePath` matches them to project files
2. Blocks with a matched file path show a file path header; blocks without a path show the code only
3. No staging or diff preview — "选择此答案" writes all blocks with file paths directly to disk

**Panel isolation**: `codeBlocksA` shows only source A blocks, `codeBlocksB` shows only source B blocks. Each panel has independent file path deduplication (`usedPathsMap` — one Set per source), so both panels can suggest different changes to the same file.

**Content filtering**: `isFileApplicable()` rejects bash/shell commands, compiler output, error traces, and blocks under 2 lines.

**File path extraction** (`extractFilePath` in `codeParser.js`):
1. Explicit labels in text before code block (e.g., "file: src/main.rs")
2. Path-like patterns (e.g., `src/foo.js`)
3. Fuzzy filename matching
4. First line of code block content (if it looks like a filename)
5. Language-to-extension fallback against project files

### Choice & Preference Submit

User clicks "选择此答案" → `handleChoice(side)` in `App.vue`:
1. Collects code blocks from selected panel (`codeBlocksA` or `codeBlocksB`)
2. Writes all blocks with file paths to disk via `fileIndexer.writeFile()` (parallel, non-blocking)
3. Sends preference data to `POST /api/preference` (fire-and-forget)
4. Shows "偏好已保存" toast
5. `updateConfidence()` updates EMA bias and round count

### Question Display

`handleSubmit` stores the question in `currentQuestion`, displays it in a user bubble with a loading spinner. `answerPanelRef.resetChoice()` is called at the start of each submission to restore both panels.

### Eye Tracking

WebGazer initialized once, then `resume()`/`pause()` per session. Camera preview hidden via DOM manipulation. Tracking indicator shows current region (详细解答/简洁解答) with side-specific color (blue/green).

### State (AnswerPanel)

- `selectedSide` — 'A' | 'B' | null, which side the user chose
- `choiceDisabled` — true after selection is made
- `overridden` — true when user manually overrides auto-selection
- `expandedA` / `expandedB` — collapse state for each panel
- `resetChoice()` — resets `selectedSide`, `choiceDisabled`, `autoSelected`, `overridden`; called on each new submission

### State (App.vue)

- `currentQuestion` — current user question text
- `answerA` / `answerB` — raw AI answer strings
- `answerSegmentsA` / `answerSegmentsB` — multi-round segment arrays (when `segments.length > 1`)
- `userPreference` — `{ finalChoice, timeOnA, timeOnB, leftToRight, rightToLeft }`
- `emaBias` / `roundCount` — confidence inference state

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

Everforest Dark Medium. Font sizes use `--font-scale: 0.7` — `--font-xs` is 8.4px, `--font-base` is 10.5px. All colors as CSS variables in `src/styles/everforest.css`.
