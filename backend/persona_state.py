"""
Persona 动态调整 + 持久化（按项目名隔离）

每轮用户选择后：
- 选中侧 → 不变
- 未选中侧 → EMA 朝向选中侧收束
- 收敛后 → 未被选中的一侧随机探索

状态文件存储在 backend/persona_states/{project_name}.json
"""

import json
import random
from pathlib import Path

from persona_loader import DIMENSION_PRIORITY, PersonaLoader

_STATES_DIR = Path(__file__).parent / "persona_states"

# 关键维度用于收敛检测
KEY_DIMS = [
    "ecosystem_maturity",
    "correctness_strategy",
    "error_handling",
    "edge_case_coverage",
    "dependency_philosophy",
]

CONVERGE_THRESHOLD = 0.5
ALPHA = 0.3
DEFAULT_PERSONA_A = "稳健派"
DEFAULT_PERSONA_B = "现代派"


# ===== 持久化 =====

def _state_path(project_name: str) -> Path:
    safe = project_name.replace("/", "_").replace("\\", "_")
    _STATES_DIR.mkdir(parents=True, exist_ok=True)
    return _STATES_DIR / f"{safe}.json"


def load_state(project_name: str = "default") -> dict:
    """加载项目状态，不存在则返回初始状态"""
    path = _state_path(project_name)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return _initial_state()


def save_state(project_name: str, state: dict):
    """持久化状态"""
    path = _state_path(project_name)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def reset_state(project_name: str):
    """删除项目状态"""
    path = _state_path(project_name)
    if path.exists():
        path.unlink()


# ===== 数据变换 =====

def _initial_state() -> dict:
    pa = PersonaLoader.load(DEFAULT_PERSONA_A)
    pb = PersonaLoader.load(DEFAULT_PERSONA_B)
    return {
        "version": 1,
        "converged": False,
        "persona_a": {
            "name": DEFAULT_PERSONA_A,
            "scores": {k: float(v) for k, v in pa.scores.items()},
        },
        "persona_b": {
            "name": DEFAULT_PERSONA_B,
            "scores": {k: float(v) for k, v in pb.scores.items()},
        },
    }


def record_choice(state: dict, chosen_side: str) -> dict:
    """记录用户选择，返回更新后的 state dict"""
    persona_a = state["persona_a"]["scores"]
    persona_b = state["persona_b"]["scores"]
    converged = state.get("converged", False)

    if chosen_side == "A":
        chosen_scores = persona_a
        other_scores = persona_b
    else:
        chosen_scores = persona_b
        other_scores = persona_a

    gap = _convergence_gap(persona_a, persona_b)
    if not converged and gap < CONVERGE_THRESHOLD:
        converged = True

    if not converged:
        for dim in DIMENSION_PRIORITY:
            if dim not in chosen_scores or dim not in other_scores:
                continue
            target = chosen_scores[dim]
            current = other_scores[dim]
            new_val = ALPHA * target + (1 - ALPHA) * current
            other_scores[dim] = round(max(1.0, min(5.0, new_val)), 2)
    else:
        _explore_random(other_scores)

    state["converged"] = converged
    return state


def get_persona_bias(state: dict) -> float:
    gap = _convergence_gap(
        state["persona_a"]["scores"],
        state["persona_b"]["scores"],
    )
    return min(1.0, gap / 4.0)


def _convergence_gap(scores_a: dict, scores_b: dict) -> float:
    gaps = []
    for dim in KEY_DIMS:
        a = scores_a.get(dim, 3.0)
        b = scores_b.get(dim, 3.0)
        gaps.append(abs(a - b))
    return sum(gaps) / len(gaps) if gaps else 0.0


def _explore_random(scores: dict):
    available_dims = [d for d in DIMENSION_PRIORITY if d in scores]
    if not available_dims:
        return
    n_dims = random.randint(1, min(2, len(available_dims)))
    for dim in random.sample(available_dims, n_dims):
        delta = random.choice([-1.0, -0.5, 0.5, 1.0])
        scores[dim] = round(max(1.0, min(5.0, scores[dim] + delta)), 2)


def get_prompt_scores(state: dict, side: str) -> dict:
    key = "persona_a" if side == "A" else "persona_b"
    return state[key]
