# Auto-Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement eye-tracking-based preference inference and auto-selection, replacing the current approach where preference feedback causes answer convergence.

**Architecture:** EMA-based confidence system (3 signals: eye bias, explicit choice, decision latency) drives 3-tier UI states. Backend no longer uses preference to modify system prompts. Experiment mode expanded to 3 groups.

**Tech Stack:** Vue 3 Composition API, Python Flask, WebGazer.js

**Spec:** `docs/specs/2026-04-08-auto-selection-design.md`

---

## File Map

| File | Change |
|---|---|
| `frontend/src/App.vue` | Add confidence state, modify handleSubmit/handleChoice, pass new props |
| `frontend/src/components/AnswerPanel.vue` | Add 3-tier UI, collapse logic, preference hint |
| `backend/app.py` | Remove preference usage in generate_dual_answers, expand experimentMode |

---

### Task 1: Backend — Remove preference influence on answers

**Files:** `backend/app.py:58-72`

- [ ] **Step 1: Remove preference-based system prompt modification**

In `app.py`, delete lines 58-72 (the `if preference:` block that appends notes to system_a/system_b). Keep the `preference` parameter in the function signature — just don't use it.

```python
# DELETE this block:
if preference:
    if preference.get("finalChoice") == "A":
        system_b += "\n注意：用户之前选择了详细解答，说明用户偏好详细解释风格。"
    elif preference.get("finalChoice") == "B":
        system_a += "\n注意：用户之前选择了简洁解答，说明用户偏好简洁直接的风格。"
    time_a = preference.get("timeOnA", 0)
    time_b = preference.get("timeOnB", 0)
    if time_a > time_b * 1.5:
        system_b += "\n注意：用户在详细解答上停留更久，可以适当增加一些解释。"
    elif time_b > time_a * 1.5:
        system_a += "\n注意：用户在简洁解答上停留更久，回答可以更精简。"
```

- [ ] **Step 2: Expand experimentMode to 3 values**

Change the control group check from binary to ternary. In the `ask()` route (line 122-124):

```python
# Before:
if experiment_mode == "control":
    preference = {}

# After:
if experiment_mode in ("control", "manual"):
    preference = {}  # manual = eye tracking on but no auto-select
```

- [ ] **Step 3: Build and verify backend starts**

```bash
backend/.venv/bin/python backend/app.py
curl http://localhost:8000/api/health
```

- [ ] **Step 4: Commit**

```bash
git add backend/app.py
git commit -m "fix: Remove preference influence on dual answer generation"
```

---

### Task 2: Frontend — Add confidence state and inference logic

**Files:** `frontend/src/App.vue`

- [ ] **Step 1: Add confidence-related state variables**

After the existing `userPreference` ref (line 27), add:

```javascript
const emaBias = ref(0.5)
const roundCount = ref(0)
const confidence = computed(() => {
  const raw = Math.min(1, Math.abs(emaBias.value - 0.5) * 4)
  const maturity = Math.min(1, roundCount.value / 3)
  return raw * maturity
})
const preferredSide = computed(() => {
  if (confidence.value < 0.5) return null
  return emaBias.value > 0.5 ? 'A' : 'B'
})
const autoMode = computed(() => confidence.value >= 0.8)
const decisionStartTime = ref(null)
```

- [ ] **Step 2: Add updateConfidence function**

```javascript
const ALPHA = 0.3
const MIN_EYE_TIME = 2000
const STRONG_WEIGHT = 0.7

function updateConfidence(eyeTimeA, eyeTimeB, explicitChoice) {
  const totalEye = eyeTimeA + eyeTimeB
  if (totalEye > MIN_EYE_TIME) {
    const rawBias = eyeTimeA / totalEye
    emaBias.value = ALPHA * rawBias + (1 - ALPHA) * emaBias.value
  }
  if (explicitChoice === 'A') {
    emaBias.value = STRONG_WEIGHT * 1.0 + (1 - STRONG_WEIGHT) * emaBias.value
  } else if (explicitChoice === 'B') {
    emaBias.value = STRONG_WEIGHT * 0.0 + (1 - STRONG_WEIGHT) * emaBias.value
  }
  roundCount.value++
}
```

- [ ] **Step 3: Modify handleSubmit to record decisionStartTime and update confidence**

In `handleSubmit`, before the API call, add:

```javascript
decisionStartTime.value = Date.now()
```

After the API response (after `answerB.value = data.answerB`), add:

```javascript
// Previous round's eye data contributes to confidence
updateConfidence(
  userPreference.value.timeOnA,
  userPreference.value.timeOnB,
  null
)
// Reset per-round eye data
userPreference.value.timeOnA = 0
userPreference.value.timeOnB = 0
```

- [ ] **Step 4: Modify handleChoice to record decisionTime and update confidence with strong signal**

At the start of `handleChoice`, calculate decision time:

```javascript
const decisionTime = decisionStartTime.value
  ? Date.now() - decisionStartTime.value
  : null
```

After setting `userPreference.value.finalChoice = side`, call:

```javascript
updateConfidence(0, 0, side)
```

Add `decisionTime` to the preference data sent to `/api/preference`.

- [ ] **Step 5: Remove preference from /api/ask request**

In `handleSubmit`, remove the line that adds `preference` to `requestBody`:

```javascript
// DELETE these lines:
if (experimentMode.value === 'treatment') {
  requestBody.preference = userPreference.value
}
```

- [ ] **Step 6: Pass new props to AnswerPanel**

Update the AnswerPanel usage:

```html
<AnswerPanel
  v-if="answerA || answerB"
  ref="answerPanelRef"
  :answerA="answerA"
  :answerB="answerB"
  :is-loading="isLoading"
  :files="indexedFiles"
  :preferred-side="preferredSide"
  :auto-mode="autoMode"
  :confidence="confidence"
  @choice="handleChoice"
  @apply-change="handleApplyChange"
  @unapply-change="handleUnapplyChange"
  @diff-toggle="handleDiffToggle"
/>
```

- [ ] **Step 7: Build to verify**

```bash
cd frontend && bun run build
```

- [ ] **Step 8: Commit**

```bash
git add frontend/src/App.vue
git commit -m "feat: Add confidence state and eye tracking inference logic"
```

---

### Task 3: Frontend — AnswerPanel 3-tier UI

**Files:** `frontend/src/components/AnswerPanel.vue`

- [ ] **Step 1: Add new props**

```javascript
const props = defineProps({
  answerA: String,
  answerB: String,
  isLoading: Boolean,
  files: Array,
  preferredSide: String,   // 'A' | 'B' | null
  autoMode: Boolean,        // true when confidence >= 0.8
  confidence: Number        // 0-1
})
```

- [ ] **Step 2: Update panel column classes for collapse/expand**

Change the template for both answer-col divs to use dynamic flex:

Panel A:
```html
<div
  class="answer-col"
  :id="regionAId"
  :class="{
    selected: selectedSide === 'A',
    hidden: choiceDisabled && selectedSide !== 'A',
    collapsed: autoMode && preferredSide === 'B',
    expanded: autoMode && preferredSide === 'A'
  }"
>
```

Panel B (same pattern with preferredSide === 'A'/'B').

- [ ] **Step 3: Add preference hint display**

Below each panel's header badge, add (only when confidence is in the 0.5-0.8 range):

```html
<span v-if="preferredSide && !autoMode" class="preference-hint">
  推断偏好: {{ preferredSide === 'A' ? '详细解答' : '简洁解答' }}
</span>
```

- [ ] **Step 4: Auto-select when autoMode is true**

Add a watcher or modify the rendering logic:

```javascript
import { watch } from 'vue'

watch(() => props.autoMode, (isAuto) => {
  if (isAuto && props.preferredSide && !selectedSide.value) {
    selectedSide.value = props.preferredSide
    choiceDisabled.value = true
  }
}, { immediate: true })
```

- [ ] **Step 5: Add "override" button when in autoMode**

When `autoMode` is true and panel is collapsed, show an expand button:

```html
<button
  v-if="autoMode && preferredSide !== (panel side)"
  class="override-btn"
  @click="handleOverride"
>
  展开对比
</button>
```

```javascript
function handleOverride() {
  selectedSide.value = null
  choiceDisabled.value = false
}
```

- [ ] **Step 6: Add CSS for collapsed/expanded states and preference hint**

```css
.answer-col.collapsed {
  flex: 0.3;
}

.answer-col.expanded {
  flex: 0.7;
}

.preference-hint {
  font-size: var(--font-xs);
  color: var(--yellow);
  padding: 2px 8px;
  background: var(--bg-yellow);
  border-radius: 4px;
}

.override-btn {
  margin: 8px 16px;
  padding: 8px 14px;
  background: var(--bg3);
  color: var(--fg);
  border: none;
  border-radius: 4px;
  font-size: var(--font-sm);
  cursor: pointer;
}

.override-btn:hover {
  background: var(--bg4);
}
```

- [ ] **Step 7: Build to verify**

```bash
cd frontend && bun run build
```

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/AnswerPanel.vue
git commit -m "feat: Add 3-tier UI for auto-selection based on confidence"
```

---

### Task 4: Experiment mode expansion

**Files:** `frontend/src/App.vue`, `backend/app.py`

- [ ] **Step 1: Update experimentMode toggle in App.vue**

Change from binary to ternary toggle:

```javascript
const experimentModes = ['full', 'manual', 'control']
const experimentMode = ref('full')

function toggleMode() {
  const idx = experimentModes.indexOf(experimentMode.value)
  experimentMode.value = experimentModes[(idx + 1) % experimentModes.length]
}
```

Update the computed `isTreatment`:
```javascript
const isTreatment = computed(() => experimentMode.value !== 'control')
```

- [ ] **Step 2: Conditionally disable eye tracking for 'manual' and 'control'**

In `handleSubmit`, the eye tracking start condition:

```javascript
// Before:
if (experimentMode.value === 'treatment' && eyeTrackerRef.value)

// After:
if (experimentMode.value === 'full' && eyeTrackerRef.value)
```

For 'manual' mode: eye tracking runs but autoMode is forced false. Add:

```javascript
const autoMode = computed(() =>
  experimentMode.value === 'full' && confidence.value >= 0.8
)
```

- [ ] **Step 3: Update toggle button label**

```html
<span class="toggle-label">
  实验模式:
  {{ experimentMode === 'full' ? '完整' : experimentMode === 'manual' ? '手动' : '对照' }}
</span>
```

- [ ] **Step 4: Build and verify**

```bash
cd frontend && bun run build
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.vue
git commit -m "feat: Expand experiment mode to full/manual/control"
```

---

### Task 5: End-to-end verification

- [ ] **Step 1: Start backend and frontend**

```bash
backend/.venv/bin/python backend/app.py &
cd frontend && bun run dev
```

- [ ] **Step 2: Test treatment mode (full)**

1. Open http://localhost:5173
2. Ask a question → verify two distinct answers appear
3. Choose one answer → verify preference recorded
4. Ask another question → verify confidence updates
5. After 3+ rounds with consistent choice → verify auto-selection kicks in

- [ ] **Step 3: Test control mode**

1. Toggle to control mode
2. Ask questions → verify eye tracking is off, no auto-selection
3. Verify answers are still distinct (no preference influence)

- [ ] **Step 4: Verify experiment data**

```bash
cat backend/experiment_data.jsonl | tail -5
```

Verify each entry contains `emaBias`, `confidence`, `decisionTime` fields.

- [ ] **Step 5: Final commit for any fixes**

```bash
git add -A && git commit -m "fix: End-to-end verification fixes"
```
