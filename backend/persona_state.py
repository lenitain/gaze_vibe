"""
Persona 动态调整（纯数据变换，无文件 I/O）

每轮用户选择后：
- 选中侧 → 不变
- 未选中侧 → EMA 朝向选中侧收束
- 收敛后 → 未被选中的一侧随机探索

前后端流程：
  前端从项目根目录读取 persona_state.json → 传给后端
  后端处理并返回更新后的 state → 前端写回文件
"""

import random
from persona_loader import PersonaLoader, Persona, DIMENSION_PRIORITY

# 关键维度用于收敛检测
KEY_DIMS = [
    "ecosystem_maturity",
    "correctness_strategy",
    "error_handling",
    "edge_case_coverage",
    "dependency_philosophy",
]

# 收敛阈值（1-5 分数制下的平均差距）
CONVERGE_THRESHOLD = 0.5

# EMA 系数
ALPHA = 0.3

DEFAULT_PERSONA_A = "稳健派"
DEFAULT_PERSONA_B = "现代派"


def initial_state() -> dict:
    """生成初始状态 dict（前端首次打开项目时用）"""
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
    """
    记录用户选择，返回更新后的 state dict

    Args:
        state: 当前 persona state dict
        chosen_side: "A" 或 "B"

    Returns:
        更新后的 state dict（原地修改 + 返回）
    """
    persona_a = state["persona_a"]["scores"]
    persona_b = state["persona_b"]["scores"]
    converged = state.get("converged", False)

    if chosen_side == "A":
        chosen_scores = persona_a
        other_scores = persona_b
    else:
        chosen_scores = persona_b
        other_scores = persona_a

    # 检测是否已收敛
    gap = _convergence_gap(persona_a, persona_b)
    if not converged and gap < CONVERGE_THRESHOLD:
        converged = True

    if not converged:
        # 收敛中：未选中侧 EMA 朝向选中侧
        for dim in DIMENSION_PRIORITY:
            if dim not in chosen_scores or dim not in other_scores:
                continue
            target = chosen_scores[dim]
            current = other_scores[dim]
            new_val = ALPHA * target + (1 - ALPHA) * current
            other_scores[dim] = round(max(1.0, min(5.0, new_val)), 2)
    else:
        # 收敛后：未被选中的一侧随机探索
        _explore_random(other_scores)

    state["converged"] = converged
    return state


def get_persona_bias(state: dict) -> float:
    """
    计算两个 Persona 之间的偏差 (0~1)

    0.0 = 完全相同, 1.0 = 差异极大
    """
    gap = _convergence_gap(
        state["persona_a"]["scores"],
        state["persona_b"]["scores"],
    )
    return min(1.0, gap / 4.0)


def _convergence_gap(scores_a: dict, scores_b: dict) -> float:
    """计算关键维度上的平均差距"""
    gaps = []
    for dim in KEY_DIMS:
        a = scores_a.get(dim, 3.0)
        b = scores_b.get(dim, 3.0)
        gaps.append(abs(a - b))
    return sum(gaps) / len(gaps) if gaps else 0.0


def _explore_random(scores: dict):
    """随机探索：在 1-2 个维度上 ±0.5~1.0 扰动"""
    available_dims = [d for d in DIMENSION_PRIORITY if d in scores]
    if not available_dims:
        return

    n_dims = random.randint(1, min(2, len(available_dims)))
    dims_to_change = random.sample(available_dims, n_dims)

    for dim in dims_to_change:
        delta = random.choice([-1.0, -0.5, 0.5, 1.0])
        scores[dim] = round(max(1.0, min(5.0, scores[dim] + delta)), 2)


def get_prompt_scores(state: dict, side: str) -> dict:
    """
    获取用于构建 prompt 的 Persona scores

    Args:
        state: persona state dict
        side: "A" 或 "B"

    Returns:
        {name, scores} dict
    """
    key = "persona_a" if side == "A" else "persona_b"
    return state[key]
