# AGENTS.md - Guide for Coding Agents

## Project Overview

GazeVibe is an eye-tracking AI programming assistant prototype. It generates dual answers (detailed vs concise) to programming questions and uses webcam-based eye tracking (WebGazer.js) to learn user reading preferences.

- **Frontend**: Vue 3 + Vite (`frontend/`)
- **Backend**: Python Flask + DeepSeek/OpenAI API (`backend/`)
- **No TypeScript** — plain JavaScript with ES modules
- **No test framework** is currently configured
- **No linter/formatter** is currently configured (though `.ruff_cache/` exists, ruff is not in requirements)

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

### Testing & Linting

No test or lint tooling is configured. When adding tests:
- Frontend: consider Vitest (`npm i -D vitest @vue/test-utils`)
- Backend: consider pytest (`pip install pytest`), then `pytest` or `pytest test_app.py`

## Code Style Guidelines

### Frontend (Vue 3)

**Vue SFC Convention**: Always use `<script setup>` (Composition API). Do not use Options API.

```vue
<script setup>
import { ref, watch } from 'vue'

const props = defineProps({ answerA: String, answerB: String })
const emit = defineEmits(['choice'])
const selected = ref(null)

function selectA() {
  selected.value = 'A'
  emit('choice', 'A')
}
</script>

<template>
  <div>{{ answerA }}</div>
</template>

<style scoped>
.answer { color: #fff; }
</style>
```

**Naming Conventions**:
- Components: PascalCase (`AnswerPanel.vue`, `ChatInput.vue`)
- Component methods/functions: camelCase (`handleSubmit`, `startTracking`)
- Refs/reactive state: camelCase (`isTracking`, `selectedSide`)
- CSS classes: kebab-case (`answer-panel`, `choose-btn`)
- Emits/events: kebab-case in templates (`@region-switch`)

**Imports**: Group by source — Vue imports first, then local components, then utilities.

**Props/Emits**: Use `defineProps` with object syntax (not runtime type-only). Use `defineEmits` with array of event names.

**Expose**: Use `defineExpose` to expose methods/refs to parent components when needed.

**Styling**: Use `<style scoped>`. Prefer class-based styling over inline styles. Color palette is dark-themed (`#1e1e1e`, `#252526`, `#333`, `#4fc3f7`).

### Backend (Python Flask)

**Formatting**: No formatter configured. Follow PEP 8 conventions visible in existing code:
- 4-space indentation
- Double quotes for strings
- Blank line between top-level definitions

**Docstrings**: Use triple-quoted docstrings for functions (Chinese is acceptable, as the project uses Chinese comments).

**Imports**: Standard library first (`os`, `json`), then third-party (`flask`, `openai`). One import per line; no wildcard imports.

**Error Handling**: Use try/except with broad `Exception` catches in route handlers. Return JSON error responses with appropriate HTTP status codes (400 for bad input, 500 for server errors).

**Route Pattern**: Define routes with `@app.route("/api/...", methods=[...])`. Keep handlers thin — delegate logic to helper functions.

**Naming**: Functions and variables: snake_case. Constants: UPPER_SNAKE_CASE (`ANTHROPIC_API_KEY`).

**API Responses**: Always return `jsonify({...})`. Include a `success: true/false` field in responses that perform actions.

### General Conventions

- **No comments unless asked** — code should be self-documenting
- **No emojis** in code or commit messages unless explicitly requested
- Keep functions focused and small
- Prefer explicit over implicit
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
│       └── components/
│           ├── AnswerPanel.vue   # Dual-answer display panel
│           ├── ChatInput.vue     # Question input component
│           └── EyeTracker.vue    # WebGazer eye tracking
├── backend/
│   ├── app.py                   # Flask API server
│   ├── requirements.txt
│   └── run.sh                   # uv-based launcher
└── README.md
```

## API Endpoints

| Method | Path              | Description                |
|--------|-------------------|----------------------------|
| POST   | `/api/ask`        | Generate dual answers      |
| POST   | `/api/preference` | Save user preference data  |
| GET    | `/api/health`     | Health check               |

## Skills

Use these skills when working on this project. Load them via the `skill` tool.

| Skill | When to use |
|-------|-------------|
| `brainstorming` | **Required** before creating features, components, or modifying behavior |
| `agent-browser` | Browser automation — navigating pages, filling forms, taking screenshots, testing WebGazer interactions |
| `code-simplifier` | Simplifying or cleaning up code for clarity and maintainability |
| `security-review` | Reviewing code for security vulnerabilities (injection, XSS, auth issues) |
| `find-bugs` | Finding bugs and code quality issues in local branch changes |
