"""
Persona 多维动态调整 + 维度级收敛（按项目名隔离）

每轮用户选择后：
- 选出侧不变，未选中侧各维度独立 EMA 朝向选中侧收束
- 各维度独立检测收敛，收敛后 A/B 共用同一分值（侧间差异消失）
- 收敛后有反转信号则解除收敛重新调整（收敛衰减）
- 各维度调整速度独立配置
- 所有维度收敛后进入随机探索模式

状态文件存储在 backend/persona_states/{project_name}.json
"""

import json
import random
from datetime import datetime
from pathlib import Path

from persona_loader import DIMENSION_DESCRIPTIONS, DIMENSION_PRIORITY, PersonaLoader

_STATES_DIR = Path(__file__).parent / "persona_states"

CONVERGE_THRESHOLD = 0.5          # 维度 A/B 差距低于此值视为收敛
MIN_DIFF_TO_ADJUST = 0.3          # A/B 差距小于此值不调整（已接近）
CONVERGE_MIN_ROUNDS = 3           # 一个维度至少经历 N 轮调整才允许收敛
UNCONVERGE_THRESHOLD = 3          # 收敛后连续 N 次选反侧 → 解除收敛
UNCONVERGE_DELTA = 1.0            # 解除收敛时创建的 A/B 差距
DEFAULT_PERSONA_A = "稳健派"
DEFAULT_PERSONA_B = "现代派"

# 每个维度的 EMA 调整速度（经验权重越高 → 收敛越快）
# 核心工程决策维度用高 alpha，风格性维度用低 alpha
DIMENSION_ALPHA: dict[str, float] = {
    "ecosystem_maturity": 0.35,       # 生态选型是强偏好
    "correctness_strategy": 0.35,     # 类型安全也是强偏好
    "error_handling": 0.40,           # 错误处理是最明显的信号
    "edge_case_coverage": 0.30,       # 边界覆盖中等
    "testing_strategy": 0.30,         # 测试策略中等
    "dependency_philosophy": 0.25,    # 依赖哲学偏保守
    "naming_style": 0.20,             # 命名风格是弱信号
    "documentation_depth": 0.20,      # 文档深度也是弱信号
    "abstraction_timing": 0.25,       # 抽象时机中等偏弱
    "performance_priority": 0.30,     # 性能优先级中等
}

# 维度的"方向"：收敛时记录选中侧，解锁反侧时判断
# True = A 侧代表高分（稳健派），False = B 侧代表高分（现代派）
# 实际由两者分数关系决定，不硬编码


# ===== 持久化 =====

def _state_path(project_name: str) -> Path:
    safe = project_name.replace("/", "_").replace("\\", "_")
    _STATES_DIR.mkdir(parents=True, exist_ok=True)
    return _STATES_DIR / f"{safe}.json"


def _log_path(project_name: str) -> Path:
    """状态变更日志路径（JSONL 格式）"""
    safe = project_name.replace("/", "_").replace("\\", "_")
    _STATES_DIR.mkdir(parents=True, exist_ok=True)
    return _STATES_DIR / f"{safe}.log.jsonl"


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
    # a_higher：该维度原始 A 分是否高于 B 分（用于解除收敛时确定分裂方向）
    initial_a_higher = {
        dim: float(pa.scores.get(dim, 3)) > float(pb.scores.get(dim, 3))
        for dim in DIMENSION_PRIORITY
    }
    return {
        "version": 3,
        "persona_a": {
            "name": DEFAULT_PERSONA_A,
            "scores": {k: float(v) for k, v in pa.scores.items()},
        },
        "persona_b": {
            "name": DEFAULT_PERSONA_B,
            "scores": {k: float(v) for k, v in pb.scores.items()},
        },
        "dimensions": {
            dim: {
                "converged": False,
                "adjustments": 0,
                "preferred_side": None,
                "opposite_count": 0,
                "a_higher": initial_a_higher.get(dim, True),
            }
            for dim in DIMENSION_PRIORITY
        },
        "all_converged": False,
    }


def classify_dimensions(question: str) -> list[str]:
    """
    通过关键词匹配判断用户问题涉及哪些 Persona 维度。

    返回维度名称列表，如 ["error_handling", "testing_strategy"]。
    若无匹配，返回空列表（表示全部维度都可能相关）。

    注意：这是关键词回退方案。推荐使用 classify_dimensions_llm() 获取更准确的结果。
    """
    q = question.lower()

    DIM_KEYWORDS = {
        "ecosystem_maturity": [
            "crate", "库", "生态", "成熟", "新工具", "stable", "beta",
            "version", "版本", "选型", "选择", "recommend", "推荐",
        ],
        "correctness_strategy": [
            "类型", "编译", "type", "static", "soundness", "unsafe",
            "安全", "类型系统", "type system", "类型安全",
        ],
        "naming_style": [
            "命名", "naming", "名称", "变量名", "function name",
            "命名规范", "命名风格",
        ],
        "documentation_depth": [
            "文档", "doc", "文档注释", "documentation", "注释",
            "comment", "文档化",
        ],
        "error_handling": [
            "错误", "error", "panic", "unwrap", "result", "anyhow",
            "thiserror", "异常", "错误处理", "异常处理", "错误类型",
            "错误传播",
        ],
        "edge_case_coverage": [
            "边界", "边界情况", "极端", "edge case", "null", "空",
            "非法", "非法输入", "异常输入", "特殊",
        ],
        "dependency_philosophy": [
            "依赖", "dependency", "包", "package", "引入",
            "第三方库", "外部依赖", "轻量",
        ],
        "abstraction_timing": [
            "抽象", "dry", "重构", "refactor", "重复", "duplicate",
            "通用", "泛化", "抽象程度",
        ],
        "testing_strategy": [
            "测试", "test", "单元测试", "集成测试", "assert", "mock",
            "property", "测试覆盖", "测试策略",
        ],
        "performance_priority": [
            "性能", "performance", "benchmark", "优化", "fast", "慢",
            "高效", "效率", "延迟", "latency", "吞吐",
        ],
    }

    matched = []
    for dim, keywords in DIM_KEYWORDS.items():
        for kw in keywords:
            if kw in q:
                matched.append(dim)
                break

    return matched


def _ensure_dim_fields(dim_info: dict, dim: str | None = None) -> dict:
    """兼容老版本 state（缺少字段时填充默认值）"""
    if "preferred_side" not in dim_info:
        dim_info["preferred_side"] = None
    if "opposite_count" not in dim_info:
        dim_info["opposite_count"] = 0
    if "a_higher" not in dim_info:
        # 老版本没有 a_higher，从当前 score 推断
        dim_info["a_higher"] = True
    return dim_info


def record_choice(state: dict, chosen_side: str, relevant_dims: list[str] | None = None) -> dict:
    """
    记录用户选择，返回更新后的 state dict。

    只调整与问题相关的维度（relevant_dims），其余维度不动。
    若 relevant_dims 为 None 或空，则调整全部未收敛维度。
    各维度独立收敛检测，收敛后有反转信号则解除收敛。
    """
    persona_a = state["persona_a"]["scores"]
    persona_b = state["persona_b"]["scores"]
    dims = state.setdefault("dimensions", {
        dim: {"converged": False, "adjustments": 0}
        for dim in DIMENSION_PRIORITY
    })

    if chosen_side == "A":
        chosen_scores = persona_a
        other_scores = persona_b
    else:
        chosen_scores = persona_b
        other_scores = persona_a

    # 确定本次调整涉及哪些维度
    if relevant_dims:
        target_dims = [d for d in DIMENSION_PRIORITY if d in relevant_dims]
    else:
        target_dims = list(DIMENSION_PRIORITY)

    all_converged = True

    for dim in DIMENSION_PRIORITY:
        if dim not in chosen_scores or dim not in other_scores:
            continue

        c_val = chosen_scores[dim]
        o_val = other_scores[dim]
        gap = abs(c_val - o_val)

        dim_info = _ensure_dim_fields(dims.get(dim, {}), dim)
        converged = dim_info.get("converged", False)
        preferred_side = dim_info.get("preferred_side")

        # ---- 已收敛维度：检测反转信号 ----
        if converged:
            if dim in target_dims and preferred_side and chosen_side != preferred_side:
                # 用户选了和收敛方向相反的一侧 → 积累计数
                dim_info["opposite_count"] = dim_info.get("opposite_count", 0) + 1
                if dim_info["opposite_count"] >= UNCONVERGE_THRESHOLD:
                    _unconverge_dim(persona_a, persona_b, dim, chosen_side, dim_info)
                    # 解除收敛后本轮的调整逻辑在后面继续执行
                    converged = False
                    dim_info["converged"] = False
                    dim_info["opposite_count"] = 0
                    dim_info["preferred_side"] = None
                else:
                    dims[dim] = dim_info
                continue
            elif dim in target_dims and preferred_side and chosen_side == preferred_side:
                # 选了一致的一侧 → 重置反侧计数
                dim_info["opposite_count"] = 0
                dims[dim] = dim_info
            continue  # 已收敛且无反转信号

        # ---- 不在 target_dims 中的维度不动 ----
        if dim not in target_dims:
            if not dim_info.get("converged", False):
                all_converged = False
            continue

        # ---- 未收敛维度：调整逻辑 ----
        alpha = DIMENSION_ALPHA.get(dim, 0.3)

        if gap < MIN_DIFF_TO_ADJUST:
            # 差距很小，标记为收敛
            avg = round((c_val + o_val) / 2, 2)
            persona_a[dim] = avg
            persona_b[dim] = avg
            dim_info["converged"] = True
            dim_info["preferred_side"] = chosen_side
            dim_info["opposite_count"] = 0
            dim_info["adjustments"] = dim_info.get("adjustments", 0) + 1
            dims[dim] = dim_info
            continue

        # 有显著差距 → EMA 调整
        new_val = alpha * c_val + (1 - alpha) * o_val
        new_val = round(max(1.0, min(5.0, new_val)), 2)
        other_scores[dim] = new_val
        dim_info["adjustments"] = dim_info.get("adjustments", 0) + 1

        # 调整后检测是否收敛
        new_gap = abs(chosen_scores[dim] - other_scores[dim])
        if new_gap < CONVERGE_THRESHOLD and dim_info["adjustments"] >= CONVERGE_MIN_ROUNDS:
            avg = round((chosen_scores[dim] + other_scores[dim]) / 2, 2)
            persona_a[dim] = avg
            persona_b[dim] = avg
            dim_info["converged"] = True
            dim_info["preferred_side"] = chosen_side
            dim_info["opposite_count"] = 0

        dims[dim] = dim_info

        if not dim_info.get("converged", False):
            all_converged = False

    # 检查所有维度是否全部收敛
    for dim in DIMENSION_PRIORITY:
        dim_info = _ensure_dim_fields(dims.get(dim, {}), dim)
        if not dim_info.get("converged", False):
            all_converged = False
            break

    state["all_converged"] = all_converged

    if all_converged:
        _explore_random(other_scores)

    return state


def _unconverge_dim(
    persona_a: dict, persona_b: dict, dim: str,
    chosen_side: str, dim_info: dict,
):
    """
    解除维度收敛：在收敛值周围按 a_higher 方向创建差距。

    分裂方向只由 a_higher 决定（不随 chosen_side 变）：
    - a_higher=True：A 高分 ←→ B 低分
    - a_higher=False：B 高分 ←→ A 低分

    收敛值本身编码了历史偏好方向（高=保守派侧，低=现代派侧），
    分裂只是在当前收敛值周围重新拉开差距。
    """
    converged_val = persona_a[dim]
    half_gap = UNCONVERGE_DELTA / 2
    a_higher = dim_info.get("a_higher", True)

    if a_higher:
        persona_a[dim] = round(min(5.0, converged_val + half_gap), 2)
        persona_b[dim] = round(max(1.0, converged_val - half_gap), 2)
    else:
        persona_a[dim] = round(max(1.0, converged_val - half_gap), 2)
        persona_b[dim] = round(min(5.0, converged_val + half_gap), 2)

    # 重置维度状态，从头开始重新收敛
    dim_info["converged"] = False
    dim_info["adjustments"] = 0
    dim_info["preferred_side"] = None
    dim_info["opposite_count"] = 0

    print(f"    [收敛衰减] {dim} 已解除收敛 (A={persona_a[dim]}, B={persona_b[dim]})")


def get_persona_bias(state: dict) -> float:
    """返回整体偏差（0~1），越大表示 A/B 差异越大"""
    gaps = []
    for dim in DIMENSION_PRIORITY:
        a = state["persona_a"]["scores"].get(dim, 3.0)
        b = state["persona_b"]["scores"].get(dim, 3.0)
        gaps.append(abs(a - b))
    avg_gap = sum(gaps) / len(gaps) if gaps else 0.0
    return min(1.0, avg_gap / 4.0)


def get_prompt_scores(state: dict, side: str) -> dict:
    """
    返回指定侧的 prompt scores。

    对于已收敛的维度，A 和 B 返回相同值（收敛平均值），
    使得侧间在该维度无差异。
    """
    dims = state.get("dimensions", {})
    base_key = "persona_a" if side == "A" else "persona_b"
    other_key = "persona_b" if side == "A" else "persona_a"
    base = state[base_key]
    other = state[other_key]

    result = {
        "name": base["name"],
        "scores": dict(base["scores"]),
    }

    for dim in DIMENSION_PRIORITY:
        dim_info = _ensure_dim_fields(dims.get(dim, {}), dim)
        if dim_info.get("converged", False):
            a_val = base["scores"].get(dim, 3.0)
            b_val = other["scores"].get(dim, 3.0)
            avg = round((a_val + b_val) / 2, 2)
            result["scores"][dim] = avg

    return result


def log_state_change(state: dict, project_name: str):
    """
    记录一次状态变更到 {project_name}.log.jsonl 文件。

    由 app.py 在 save_state 后调用，确保 project_name 可用。
    """
    if "dimensions" not in state:
        return

    dims = state["dimensions"]
    record = {
        "timestamp": datetime.now().isoformat(),
        "all_converged": state.get("all_converged", False),
        "persona_bias": state.get("persona_bias", 0.0),
        "dimensions": {
            dim: {
                "converged": info.get("converged", False),
                "adjustments": info.get("adjustments", 0),
                "preferred_side": info.get("preferred_side"),
                "opposite_count": info.get("opposite_count", 0),
            }
            for dim, info in dims.items()
        },
        "persona_a_scores": dict(state.get("persona_a", {}).get("scores", {})),
        "persona_b_scores": dict(state.get("persona_b", {}).get("scores", {})),
    }

    path = _log_path(project_name)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _explore_random(scores: dict):
    """所有维度收敛后，随机扰动以保持探索"""
    available_dims = [d for d in DIMENSION_PRIORITY if d in scores]
    if not available_dims:
        return
    n_dims = random.randint(1, min(2, len(available_dims)))
    for dim in random.sample(available_dims, n_dims):
        delta = random.choice([-1.0, -0.5, 0.5, 1.0])
        scores[dim] = round(max(1.0, min(5.0, scores[dim] + delta)), 2)
