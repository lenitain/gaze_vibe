#!/usr/bin/env python3
"""
GazeVibe 合成实验数据生成器

生成 5 个场景（A~E）的模拟实验数据，覆盖论文第 5 章描述的所有实验条件。
数据格式与 backend/app.py save_preference() 输出完全一致。

用法:
    cd scripts && uv run python generate_synthetic_data.py

输出:
    backend/experiment_data.jsonl  （约 210 条记录）
"""

import json
import math
import random
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

# 种子固定，结果可复现
RNG = np.random.default_rng(42)

# 场景参数
SCENE_A_ROUNDS = 50   # 偏好收敛
SCENE_B_ROUNDS = 60   # 模式对比 (20 per mode)
SCENE_C_ROUNDS = 30   # 归一化效果
SCENE_D_ROUNDS = 40   # 偏好反转
SCENE_E_ROUNDS = 30   # 维度分类
TOTAL_ROUNDS = SCENE_A_ROUNDS + SCENE_B_ROUNDS + SCENE_C_ROUNDS + SCENE_D_ROUNDS + SCENE_E_ROUNDS

# 10 维工程决策维度名称
DIMS = [
    "ecosystem_maturity", "correctness_strategy", "error_handling",
    "edge_case_coverage", "testing_strategy", "dependency_philosophy",
    "naming_style", "documentation_depth", "abstraction_timing",
    "performance_priority",
]


def normal_clamp(mean, std, lo=0.0, hi=1.0):
    """正态分布采样后钳制到 [lo, hi]"""
    val = RNG.normal(mean, std)
    return max(lo, min(hi, val))


def gen_norm_gaze_bias(chosen_side: str, strength: float = 0.65) -> float:
    """
    生成归一化注视偏向（每字符注视时间比）。
    不受答案长度影响，反映真实偏好。
    选择 A 时 norm_bias > 0.5，选择 B 时 < 0.5。
    strength 控制偏离 0.5 的程度。
    """
    if chosen_side == "A":
        return normal_clamp(strength, 0.10)
    elif chosen_side == "B":
        return 1.0 - normal_clamp(strength, 0.10)
    return 0.5


def raw_from_norm(norm_bias: float, len_a: int, len_b: int) -> float:
    """
    从归一化注视偏向反推原始 gazeBias（受答案长度影响）。
    
    归一化偏向 = (timeA/lenA) / (timeA/lenA + timeB/lenB)
    原始偏向 = timeA / (timeA + timeB)
    
    推导:
    let r = norm_bias / (1 - norm_bias)    # 单位时间比
    then timeA / timeB = r * lenA / lenB
    so raw_bias = (r * lenA / lenB) / (1 + r * lenA / lenB)
    """
    if abs(norm_bias - 0.5) < 0.001:
        return 0.5
    r = norm_bias / (1.0 - norm_bias)  # 单位时间比
    len_ratio = len_a / max(1, len_b)
    raw_ratio = r * len_ratio
    raw_bias = raw_ratio / (1.0 + raw_ratio)
    return max(0.01, min(0.99, raw_bias))


def gen_time_distribution(gaze_bias: float, total_time: int) -> tuple[int, int]:
    """根据注视偏向将总时间分配到两侧"""
    time_a = int(total_time * gaze_bias)
    time_b = total_time - time_a
    return time_a, time_b


def gen_eye_metrics(
    chosen_side: str, gaze_bias: float, time_on_a: int, time_on_b: int,
    total_time: int, scene_mode: str = "full"
) -> dict | None:
    """生成模拟眼动指标"""
    if scene_mode == "control":
        return None

    total_s = total_time / 1000.0

    # 扫视频率：与总时间成正比，加入噪声
    base_saccades = int(total_s * RNG.uniform(1.5, 4.0))
    saccade_count = max(1, base_saccades + int(RNG.normal(0, 2)))

    # 切换方向（含方向倾向）：选B时B→A（回视）更多，directionRatio更低
    if chosen_side == "A":
        direction_ratio = RNG.uniform(0.45, 0.75)  # A→B为主
    else:
        direction_ratio = RNG.uniform(0.25, 0.55)  # B→A（回视）更多

    left_to_right = int(saccade_count * direction_ratio)
    right_to_left = saccade_count - left_to_right
    # regressionRate 从实际切换计数推导，确保 directionRatio + regressionRate ≡ 1
    regression_rate = right_to_left / max(1, saccade_count)

    # 首次注视：多数情况下先看 A（左侧），受 gazeBias 影响
    first_region = "A" if RNG.uniform(0, 1) < 0.65 else "B"
    first_duration = int(RNG.exponential(500) + 200)

    # 注视时长方差：犹豫时更大
    is_hesitant = abs(gaze_bias - 0.5) < 0.08
    fix_var = int(RNG.exponential(200000) + 50000) if is_hesitant else int(RNG.exponential(80000) + 30000)

    # 切换间隔
    mean_switch = int(RNG.exponential(3000) + 1000) if saccade_count > 0 else 0
    switch_decay = RNG.uniform(-0.3, 0.3)

    # 探索比：前 1/3 时间的扫视比例
    exploration_ratio = normal_clamp(0.4, 0.12, 0.0, 1.0)

    # 注视熵
    p_a = time_on_a / max(1, total_time)
    p_b = time_on_b / max(1, total_time)
    tau = -(p_a * math.log(p_a) if p_a > 0 else 0) - (p_b * math.log(p_b) if p_b > 0 else 0)

    # 熵变化率
    entropy_change = RNG.uniform(-0.3, 0.3)

    # 决策延迟
    decision_latency = total_time

    # 最终注意力焦点（最后 30% 时间）
    final_a = int(time_on_a * RNG.uniform(0.2, 0.5))
    final_b = int(time_on_b * RNG.uniform(0.2, 0.5))

    return {
        "tau": round(tau, 4),
        "gazeBias": round(gaze_bias, 4),
        "regressionRate": round(regression_rate, 4),
        "saccadeCount": saccade_count,
        "directionRatio": round(direction_ratio, 4),
        "firstFixationRegion": first_region,
        "firstFixationDuration": first_duration,
        "lastFixationRegion": first_region if RNG.uniform(0, 1) < 0.5 else ("B" if first_region == "A" else "A"),
        "fixationDurationVariance": fix_var,
        "meanSwitchInterval": mean_switch,
        "switchIntervalDecay": round(switch_decay, 4),
        "decisionLatency": decision_latency,
        "explorationRatio": round(exploration_ratio, 4),
        "entropyChangeRate": round(entropy_change, 4),
        "totalDurationA": time_on_a,
        "totalDurationB": time_on_b,
        "finalAttentionFocus": {"A": final_a, "B": final_b},
    }


def sim_ema_update(old_val, current_val, alpha=0.3):
    """模拟 EMA 更新"""
    return alpha * current_val + (1 - alpha) * old_val


def sim_persona_scores(round_idx, chosen_side, persona_scores, alpha_map=None):
    """
    模拟 Persona 维度分数更新。
    返回 (updated_scores, converged_dims)
    """
    if alpha_map is None:
        alpha_map = {d: 0.3 for d in DIMS}  # 统一简化

    chosen_persona = persona_scores[chosen_side]
    other_persona = persona_scores["B" if chosen_side == "A" else "A"]

    converged = []
    for dim in DIMS:
        c = chosen_persona.get(dim, 3.0)
        o = other_persona.get(dim, 3.0)
        gap = abs(c - o)
        if gap < 0.5:
            converged.append(dim)
            continue
        alpha = alpha_map.get(dim, 0.3)
        new_o = round(alpha * c + (1 - alpha) * o, 2)
        new_o = max(1.0, min(5.0, new_o))
        other_persona[dim] = new_o
        new_gap = abs(c - new_o)
        if new_gap < 0.5:
            converged.append(dim)

    return persona_scores, converged


def gen_experiment_record(
    scene_id: str,
    round_num: int,
    experiment_mode: str,
    chosen_side: str,
    current_question: str = "",
    answer_a_length: int = 800,
    answer_b_length: int = 400,
    control_side: str = "",
    expected_dim: str = "",
    ema_state: dict | None = None,
    persona_scores: dict | None = None,
) -> dict:
    """生成一条完整的实验数据记录"""
    # 总注视时间
    total_time = int(RNG.uniform(3000, 12000))
    len_a = max(1, answer_a_length)
    len_b = max(1, answer_b_length)

    # 注视偏向：先生成（长度无关的）真实偏好，再反推原始 gazeBias
    if experiment_mode == "control":
        norm_bias = 0.5
        time_a = time_b = total_time // 2
        raw_bias = 0.5
    else:
        strength = min(0.85, 0.55 + round_num * 0.008)  # 随轮次收敛更强
        norm_bias = gen_norm_gaze_bias(chosen_side, strength)
        raw_bias = raw_from_norm(norm_bias, len_a, len_b)
        time_a, time_b = gen_time_distribution(raw_bias, total_time)

    # eyeMetrics 中的 gazeBias 用原始值（受长度影响）
    eye_metrics = gen_eye_metrics(chosen_side, raw_bias, time_a, time_b, total_time, experiment_mode)

    # 无眼动数据的模式
    if experiment_mode == "control":
        eye_metrics = None

    # 计算衍生指标（归一化后用 norm_bias）
    tpc_a = time_a / len_a
    tpc_b = time_b / len_b
    total_tpc = tpc_a + tpc_b
    norm_gaze = round(tpc_a / total_tpc, 4) if total_tpc > 0 else 0.5

    # EMA 状态
    if ema_state is not None:
        current_detail = norm_gaze
        current_explanation = norm_gaze * 0.4 + 0.3  # 简单模拟
        old_detail = ema_state.get("detail_score", 0.5)
        old_explanation = ema_state.get("explanation_score", 0.5)
        new_detail = round(sim_ema_update(old_detail, current_detail), 4)
        new_explanation = round(sim_ema_update(old_explanation, current_explanation), 4)
        new_bias = round((new_detail + new_explanation) / 2, 4)
        new_round = ema_state.get("round_count", 0) + 1
        pre = {"detail_score": old_detail, "explanation_score": old_explanation,
               "persona_bias": ema_state.get("persona_bias", 0.5), "round_count": ema_state.get("round_count", 0)}
        post = {"detail_score": new_detail, "explanation_score": new_explanation,
                "persona_bias": new_bias, "round_count": new_round}
        # 更新 ema_state
        ema_state["detail_score"] = new_detail
        ema_state["explanation_score"] = new_explanation
        ema_state["persona_bias"] = new_bias
        ema_state["round_count"] = new_round
    else:
        pre = {"detail_score": 0.5, "explanation_score": 0.5, "persona_bias": 0.5, "round_count": 0}
        post = {"detail_score": 0.5, "explanation_score": 0.5, "persona_bias": 0.5, "round_count": 0}

    # 前端 emaBias 模拟（与后端略不同）
    frontend_bias = post["persona_bias"] + RNG.uniform(-0.03, 0.03)
    frontend_confidence = min(1.0, abs(post["persona_bias"] - 0.5) * 4) * min(1.0, post["round_count"] / 3)

    # Persona 分数
    persona_snapshot = None
    if persona_scores is not None:
        updated, converged = sim_persona_scores(round_num - 1, chosen_side, persona_scores)
        # 构建快照
        a_side = persona_scores.get("A", {})
        b_side = persona_scores.get("B", {})
        dims_info = {}
        for d in DIMS:
            dims_info[d] = {
                "converged": d in converged,
                "adjustments": round_num,
                "preferred_side": chosen_side if d in converged else None,
                "opposite_count": 0,
            }
        persona_snapshot = {
            "persona_a_scores": dict(a_side),
            "persona_b_scores": dict(b_side),
            "dimensions": dims_info,
            "all_converged": len(converged) >= len(DIMS),
        }

    record = {
        "scene_id": scene_id,
        "expected_dim": expected_dim,
        "control_side": control_side,
        "projectName": f"scene_{scene_id}",
        "experimentMode": experiment_mode,
        "currentQuestion": current_question,
        "timestamp": (datetime(2026, 5, 1) + timedelta(minutes=round_num * 3)).isoformat(),
        "finalChoice": chosen_side,
        "preference": {
            "finalChoice": chosen_side,
            "timeOnA": time_a,
            "timeOnB": time_b,
            "leftToRight": RNG.integers(2, 15) if eye_metrics else 0,
            "rightToLeft": RNG.integers(2, 15) if eye_metrics else 0,
        },
        "decisionTimeMs": int(RNG.uniform(3000, 15000)),
        "eyeMetrics": eye_metrics,
        "hasEyeMetrics": eye_metrics is not None,
        "answerALength": answer_a_length,
        "answerBLength": answer_b_length,
        "derived": {
            "totalTime": total_time,
            "lengthRatio": round(len_a / max(1, len_b), 4),
            "normalizedGazeBias": norm_gaze,
        },
        "preUpdate": pre,
        "postUpdate": post,
        "adjustments": post,
        "frontend": {
            "emaBias": round(frontend_bias, 4),
            "confidence": round(frontend_confidence, 4),
        },
        "processedScores": {
            "detail_score": round(current_detail, 4) if eye_metrics else None,
            "explanation_score": round(current_explanation, 4) if eye_metrics else None,
            "components": {},
        } if eye_metrics else None,
        "personaState": persona_snapshot,
    }
    return record


def generate_scene_a(output, ema_state, persona_scores):
    """场景 A：偏好收敛 — 前 30 选 A，后 20 选 B"""
    print(f"  [A] 生成 {SCENE_A_ROUNDS} 条 (前30选A, 后20选B)...")
    for i in range(SCENE_A_ROUNDS):
        side = "A" if i < 30 else "B"
        rec = gen_experiment_record(
            scene_id="A", round_num=i + 1, experiment_mode="full",
            chosen_side=side,
            answer_a_length=int(RNG.uniform(600, 1200)),
            answer_b_length=int(RNG.uniform(250, 600)),
            ema_state=ema_state, persona_scores=persona_scores,
        )
        output.append(rec)


def generate_scene_b(output, ema_state, persona_scores):
    """场景 B：模式对比 — 各 20 轮 full/manual/control"""
    print(f"  [B] 生成 {SCENE_B_ROUNDS} 条 (各20轮 full/manual/control)...")
    modes = ["full"] * 20 + ["manual"] * 20 + ["control"] * 20
    RNG.shuffle(modes)
    for i, mode in enumerate(modes):
        side = "A" if RNG.uniform(0, 1) < 0.55 else "B"
        rec = gen_experiment_record(
            scene_id="B", round_num=i + 1, experiment_mode=mode,
            chosen_side=side,
            answer_a_length=800, answer_b_length=400,
            ema_state=ema_state if mode != "control" else None,
            persona_scores=persona_scores,
        )
        if mode == "control":
            rec["eyeMetrics"] = None
            rec["hasEyeMetrics"] = False
        output.append(rec)


def generate_scene_c(output, ema_state, persona_scores):
    """场景 C：归一化效果 — 长短差异交替"""
    print(f"  [C] 生成 {SCENE_C_ROUNDS} 条 (长短差异交替)...")
    for i in range(SCENE_C_ROUNDS):
        # 前半：长短差异大、后半：长短接近
        if i < 15:
            len_a = int(RNG.uniform(1000, 2000))
            len_b = int(RNG.uniform(200, 500))
        else:
            len_a = int(RNG.uniform(400, 800))
            len_b = int(RNG.uniform(300, 700))
        side = "A" if RNG.uniform(0, 1) < 0.55 else "B"
        rec = gen_experiment_record(
            scene_id="C", round_num=i + 1, experiment_mode="full",
            chosen_side=side,
            answer_a_length=len_a, answer_b_length=len_b,
            ema_state=ema_state, persona_scores=persona_scores,
        )
        output.append(rec)


def generate_scene_d(output, ema_state, persona_scores):
    """场景 D：偏好反转 — 前 20 选 A，后 20 选 B"""
    print(f"  [D] 生成 {SCENE_D_ROUNDS} 条 (前20选A, 后20选B)...")
    for i in range(SCENE_D_ROUNDS):
        side = "A" if i < 20 else "B"
        rec = gen_experiment_record(
            scene_id="D", round_num=i + 1, experiment_mode="full",
            chosen_side=side,
            answer_a_length=800, answer_b_length=400,
            ema_state=ema_state, persona_scores=persona_scores,
        )
        output.append(rec)


def generate_scene_e(output, ema_state, persona_scores):
    """场景 E：维度分类 — 每个维度 3 题"""
    print(f"  [E] 生成 {SCENE_E_ROUNDS} 条 (10维度×3题)...")
    dim_questions = {
        "ecosystem_maturity": [
            "我想给我的 Rust 项目加一个缓存库，应该用 chachacache 还是 moka？",
            "Web 框架选 axum 还是 actix-web？",
            "有个叫 prismite 的新 ORM 才 2k star，能用吗？",
        ],
        "correctness_strategy": [
            "Rust 里所有地方都 match 还是允许用 unwrap？",
            "结构体字段这么多，搞个 builder 还是靠运行时检查？",
            "编译通过了就一定安全了吗？要不要额外加运行时断言？",
        ],
        "error_handling": [
            "这个函数可能失败，应该返回 Result 还是直接 panic？",
            "用 anyhow 做快速开发还是用 thiserror 定义精细错误类型？",
            "调用外部 API 出错应该传播错误还是包一层自定义错误？",
        ],
        "edge_case_coverage": [
            "函数参数为空数组的时候应该返回空还是报错？",
            "用户输入全是空格要不要单独处理？",
            "并发场景下这段计数逻辑有没有竞态？",
        ],
        "testing_strategy": [
            "这个模块要不要写单元测试？还是集成测试覆盖就够了？",
            "测试数据库用 mock 还是起一个真实实例？",
            "Property-based testing 和 example-based，哪个更合适？",
        ],
        "dependency_philosophy": [
            "就解析个 JSON，要不要加 serde 还是自己手写 parser？",
            "我只用到 clap 的 basic 功能，要不要为这个加一整包依赖？",
            "这个 util 社区有现成的但我只用到一个函数，复制代码还是加依赖？",
        ],
        "naming_style": [
            "局部变量用 `ret` 还是 `result_data`？哪种更合适？",
            "这个函数名用 `parse` 还是 `parse_input_string`？",
            "Rust 里单字母变量名能不能接受？比如 `(i, v)` 中的 i 和 v。",
        ],
        "documentation_depth": [
            "公共 API 要不要每个函数都写文档注释？包括显而易见的？",
            "内部的私有辅助函数需要写 doc 吗？",
            "项目要不要强约束所有 pub fn 都有 /// 文档？",
        ],
        "abstraction_timing": [
            "这段代码在两个地方重复了，要不要立刻抽成公共函数？",
            "三个类似的结构体，要不要现在就用泛型统一？",
            "现在只有一处用到这个逻辑但未来肯定复用，提前抽象好吗？",
        ],
        "performance_priority": [
            "这个热点路径要不要用 unsafe 优化？还是保持安全但稍慢的版本？",
            "选 HashMap 还是 BTreeMap？这个场景性能差多少？",
            "这段代码可读性差但比可读版本快 2 倍，要不要用快的？",
        ],
    }
    idx = 0
    for dim, questions in dim_questions.items():
        for q in questions:
            side = "A" if RNG.uniform(0, 1) < 0.55 else "B"
            rec = gen_experiment_record(
                scene_id="E", round_num=idx + 1, experiment_mode="full",
                chosen_side=side, current_question=q,
                expected_dim=dim,
                answer_a_length=int(RNG.uniform(600, 1200)),
                answer_b_length=int(RNG.uniform(250, 600)),
                ema_state=ema_state, persona_scores=persona_scores,
            )
            output.append(rec)
            idx += 1


def main():
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    output_path = project_root / "backend" / "experiment_data.jsonl"

    print("=" * 60)
    print("  GazeVibe 合成实验数据生成器")
    print("=" * 60)
    print()

    # 初始化 EMA 状态（模拟后端 eye_processor 的跨轮次状态）
    ema_state = {"detail_score": 0.5, "explanation_score": 0.5, "persona_bias": 0.5, "round_count": 0}

    # 初始化 Persona 分数（模拟后端 persona_state 的 A/B 初始分数）
    # 从 YAML 默认值模拟（稳健派高分 ~4，现代派低分 ~2）
    persona_scores = {
        "A": {d: round(RNG.uniform(3.5, 4.5), 1) for d in DIMS},
        "B": {d: round(RNG.uniform(1.5, 2.5), 1) for d in DIMS},
    }

    output = []

    print("生成场景数据...")
    print()

    # 场景 A ~ E
    generate_scene_a(output, ema_state, persona_scores)
    generate_scene_b(output, ema_state, persona_scores)
    generate_scene_c(output, ema_state, persona_scores)
    generate_scene_d(output, ema_state, persona_scores)
    generate_scene_e(output, ema_state, persona_scores)

    # 转换所有 numpy 类型为原生 Python 类型
    def _clean(obj):
        if isinstance(obj, dict):
            return {k: _clean(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [_clean(v) for v in obj]
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return _clean(obj.tolist())
        return obj

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for rec in output:
            f.write(json.dumps(_clean(rec), ensure_ascii=False) + "\n")

    # 场景分布统计
    from collections import Counter
    scene_counts = Counter(r["scene_id"] for r in output)
    mode_counts = Counter(r["experimentMode"] for r in output)
    choice_counts = Counter(r["finalChoice"] for r in output)
    eye_count = sum(1 for r in output if r["hasEyeMetrics"])

    print(f"  写入 {len(output)} 条到 {output_path}")
    print()
    print("  === 统计摘要 ===")
    print(f"  场景分布: {dict(scene_counts)}")
    print(f"  模式分布: {dict(mode_counts)}")
    print(f"  选择分布: {dict(choice_counts)}")
    print(f"  含眼动数据: {eye_count}/{len(output)} ({eye_count/len(output)*100:.0f}%)")
    print(f"  平均注视时长: {np.mean([r['derived']['totalTime'] for r in output]):.0f}ms")
    print()

    # 按场景统计一致性率
    print("  === 按场景的一致性率 (gazeBias -> finalChoice) ===")
    for sid in sorted(scene_counts):
        scene_data = [r for r in output if r["scene_id"] == sid and r["hasEyeMetrics"]]
        if not scene_data:
            continue
        consistent = 0
        for r in scene_data:
            gb = r.get("derived", {}).get("normalizedGazeBias", 0.5)
            fc = r["finalChoice"]
            if (gb > 0.5 and fc == "A") or (gb < 0.5 and fc == "B"):
                consistent += 1
        rate = consistent / len(scene_data) * 100
        print(f"    场景 {sid}: {rate:.1f}% ({consistent}/{len(scene_data)})")

    # 归一化算法效果
    print()
    print("  === 归一化算法效果 ===")
    c_data = [r for r in output if r["scene_id"] == "C" and r["hasEyeMetrics"]]
    if c_data:
        # 长度差异大 vs 小
        large_diff = [r for r in c_data if r["derived"]["lengthRatio"] > 2 or r["derived"]["lengthRatio"] < 0.5]
        small_diff = [r for r in c_data if r["derived"]["lengthRatio"] <= 2 and r["derived"]["lengthRatio"] >= 0.5]

        def calc_rate(data, use_raw=False):
            consistent = 0
            total = 0
            for r in data:
                if use_raw:
                    gb = r["eyeMetrics"]["gazeBias"] if r["eyeMetrics"] else 0.5
                else:
                    gb = r["derived"]["normalizedGazeBias"]
                fc = r["finalChoice"]
                if pd.isna(fc):
                    continue
                total += 1
                if (gb > 0.5 and fc == "A") or (gb < 0.5 and fc == "B"):
                    consistent += 1
            return consistent / max(1, total) * 100

        print(f"    长度差异大 (n={len(large_diff)}): 原始={calc_rate(large_diff, True):.1f}% → 归一化={calc_rate(large_diff):.1f}%")
        print(f"    长度差异小 (n={len(small_diff)}): 原始={calc_rate(small_diff, True):.1f}% → 归一化={calc_rate(small_diff):.1f}%")
        print(f"    全样本 (n={len(c_data)}): 原始={calc_rate(c_data, True):.1f}% → 归一化={calc_rate(c_data):.1f}%")

    print()
    print("  完成！")


if __name__ == "__main__":
    import pandas as pd  # only for isna check
    main()
