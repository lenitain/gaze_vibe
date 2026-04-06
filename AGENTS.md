# AGENTS.md - Guide for Coding Agents

## Project Overview

GazeVibe is an eye-tracking AI programming assistant prototype. It generates dual answers (detailed vs concise) to programming questions and uses webcam-based eye tracking (WebGazer.js) to learn user reading preferences.

- **Frontend**: Vue 3 + Vite (`frontend/`)
- **Backend**: Python Flask + DeepSeek/OpenAI API (`backend/`)
- **No TypeScript** — plain JavaScript with ES modules
- **No test framework** is currently configured
- **No linter/formatter** is currently configured

## Build & Run Commands

### Frontend

```bash
cd frontend
bun install          # or npm install (bun.lock present)
bun run dev          # Dev server at http://localhost:5173
bun run build        # Production build
bun run preview      # Preview production build
```

### Backend

```bash
cd backend
pip install -r requirements.txt
python app.py        # Server at http://localhost:8000

# Or use uv (preferred if available):
bash run.sh          # Creates venv, installs deps, runs app
```

### Environment Variables

```bash
export DEEPSEEK_API_KEY="your-api-key"   # Required for LLM features
# Backend falls back to "your-api-key-here" if unset
```

### Health Check

```bash
curl http://localhost:8000/api/health
```

## Code Style Guidelines

### Frontend (Vue 3)

**Vue SFC Convention**: Always use `<script setup>` (Composition API). Do not use Options API.

**Naming Conventions**:
- Components: PascalCase (`AnswerPanel.vue`, `ChatInput.vue`)
- Component methods/functions: camelCase (`handleSubmit`, `startTracking`)
- Refs/reactive state: camelCase (`isTracking`, `selectedSide`)
- CSS classes: kebab-case (`answer-panel`, `choose-btn`)
- Emits/events: kebab-case in templates (`@region-switch`)

**Imports**: Group by source — Vue imports first, then local components, then utilities.

**Props/Emits**: Use `defineProps` with object syntax (not runtime type-only). Use `defineEmits` with array of event names.

**Styling**: Use `<style scoped>`. Prefer class-based styling over inline styles. Use CSS variables from `styles/everforest.css` (Everforest Dark Medium theme).

### Backend (Python Flask)

**Formatting**: Follow PEP 8 conventions:
- 4-space indentation
- Double quotes for strings
- Blank line between top-level definitions

**Error Handling**: Use try/except with broad `Exception` catches in route handlers. Return JSON error responses with appropriate HTTP status codes (400 for bad input, 500 for server errors).

**Route Pattern**: Define routes with `@app.route("/api/...", methods=[...])`. Keep handlers thin — delegate logic to helper functions.

**API Responses**: Always return `jsonify({...})`. Include a `success: true/false` field in responses that perform actions.

### General Conventions

- **No comments unless asked**
- **No emojis** in code or commit messages unless explicitly requested
- API proxy: Vite proxies `/api` requests to `http://localhost:8000` (see `vite.config.js`)

## Project Structure

```
gaze-vibe/
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── main.js
│       ├── App.vue
│       ├── styles/
│       │   └── everforest.css    # Theme CSS variables
│       ├── components/
│       │   ├── AnswerPanel.vue   # Dual-answer display
│       │   ├── ChatInput.vue     # Question input
│       │   ├── EyeTracker.vue    # WebGazer eye tracking
│       │   ├── FolderSelector.vue # Local folder picker (File System Access API)
│       │   ├── FileTree.vue      # File tree sidebar
│       │   ├── FileTreeNode.vue  # Recursive tree node
│       │   └── FileViewer.vue    # File content preview
│       └── utils/
│           ├── fileIndexer.js    # Index local project files
│           └── fileSelector.js   # Smart file selection for AI context
├── backend/
│   ├── app.py                   # Flask API server
│   ├── requirements.txt
│   └── run.sh                   # uv-based launcher
└── README.md
```

## API Endpoints

| Method | Path              | Description                |
|--------|-------------------|----------------------------|
| POST   | `/api/ask`        | Generate dual answers (accepts `contextFiles` for project code) |
| POST   | `/api/preference` | Save user preference data  |
| GET    | `/api/health`     | Health check               |

## Key Architecture Notes

**File System Access**: Uses browser's File System Access API (`window.showDirectoryPicker`) to read local project files. Requires Chrome 86+. Users select a folder on startup; files are indexed in memory.

**Eye Tracking Lifecycle**: WebGazer is initialized once, then uses `resume()`/`pause()` for subsequent tracking sessions. Camera preview is hidden via DOM manipulation when tracking stops.

**Smart File Selection**: When user asks a question, `fileSelector.js` scores files by keyword relevance and sends top matches to the backend as `contextFiles`.

## Theme

Uses Everforest Dark Medium palette. All colors are CSS variables defined in `src/styles/everforest.css`:
- Backgrounds: `--bg0` to `--bg5`
- Foreground: `--fg`
- Accents: `--blue`, `--green`, `--aqua`, `--red`, `--yellow`, `--purple`
- Greys: `--grey0`, `--grey1`, `--grey2`
- Font sizes: `--font-xs` (12px) to `--font-4xl` (28px)

## Skills

Use these skills when working on this project. Load them via the `skill` tool.

| Skill | When to use |
|-------|-------------|
| `brainstorming` | **Required** before creating features, components, or modifying behavior |
| `agent-browser` | Browser automation — navigating pages, filling forms, screenshots, testing WebGazer |
| `code-simplifier` | Simplifying or cleaning up code |
| `security-review` | Reviewing code for security vulnerabilities |
| `find-bugs` | Finding bugs and code quality issues |
