#!/usr/bin/env python3
"""
Persona 系统分析脚本

分析 persona_states/ 下的状态文件和变更日志：
- 维度级收敛状态与速率
- 收敛/衰减事件追踪
- 各维度 A/B 分数演化轨迹
- 跨项目对比
"""

import json
import sys
from pathlib import Path

import pandas as pd
import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).parent.parent
STATES_DIR = PROJECT_ROOT / "backend" / "persona_states"
FIGURES_DIR = PROJECT_ROOT / "docs" / "figures"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

DIMS_LABEL = {
    "ecosystem_maturity": "生态成熟度",
    "correctness_strategy": "正确性策略",
    "naming_style": "命名风格",
    "documentation_depth": "文档深度",
    "error_handling": "错误处理",
    "edge_case_coverage": "边界覆盖",
    "dependency_philosophy": "依赖哲学",
    "abstraction_timing": "抽象时机",
    "testing_strategy": "测试策略",
    "performance_priority": "性能优先级",
}


# ===== 数据加载 =====

def find_projects() -> list[str]:
    """从 JSON 状态文件发现项目名称"""
    projects = set()
    for f in STATES_DIR.glob("*.json"):
        name = f.stem
        if not name.endswith(".log"):
            projects.add(name)
    return sorted(projects)


def load_current_state(project: str) -> dict | None:
    path = STATES_DIR / f"{project}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def load_state_log(project: str) -> list[dict]:
    path = STATES_DIR / f"{project}.log.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").strip().split("\n") if line]


# ===== 分析函数 =====

def analyze_state_summary(project: str, state: dict) -> dict:
    """当前状态摘要"""
    dims = state.get("dimensions", {})
    a_scores = state.get("persona_a", {}).get("scores", {})
    b_scores = state.get("persona_b", {}).get("scores", {})

    converged = sum(1 for d in dims.values() if d.get("converged"))
    total = len(dims)

    gaps = {dim: abs(a_scores.get(dim, 0) - b_scores.get(dim, 0)) for dim in dims}
    avg_gap = np.mean(list(gaps.values())) if gaps else 0

    return {
        "project": project,
        "total_dims": total,
        "converged_dims": converged,
        "convergence_rate": converged / total if total > 0 else 0,
        "avg_a_b_gap": round(avg_gap, 3),
        "all_converged": state.get("all_converged", False),
    }


def analyze_log_timeline(project: str, log: list[dict]) -> dict:
    """从日志提取时间线"""
    if not log:
        return {"converge_events": [], "unconverge_events": [], "score_trajectory": {}}

    converge_events = []
    unconverge_events = []
    score_trajectory: dict[str, list] = {}

    for i, record in enumerate(log):
        dims = record.get("dimensions", {})
        a_scores = record.get("persona_a_scores", {})
        b_scores = record.get("persona_b_scores", {})

        for dim, info in dims.items():
            if dim not in score_trajectory:
                score_trajectory[dim] = []
            score_trajectory[dim].append({
                "step": i + 1,
                "a": a_scores.get(dim, 0),
                "b": b_scores.get(dim, 0),
                "gap": abs(a_scores.get(dim, 0) - b_scores.get(dim, 0)),
                "converged": info.get("converged", False),
                "adjustments": info.get("adjustments", 0),
            })

            # 收敛事件：从 converged=False → True
            if info.get("converged") and info.get("adjustments", 0) >= 3:
                prev_gap = abs(a_scores.get(dim, 0) - b_scores.get(dim, 0))
                if prev_gap < 0.6:  # 接近收敛
                    converge_events.append({
                        "dim": dim,
                        "step": i + 1,
                        "preferred_side": info.get("preferred_side"),
                        "final_score": a_scores.get(dim, 0),
                    })

            # 衰减事件：converged=False + adjustments=0（被重置）
            if not info.get("converged") and info.get("adjustments", 0) == 0 and i > 0:
                prev_record = log[i - 1]
                prev_dims = prev_record.get("dimensions", {})
                prev_info = prev_dims.get(dim, {})
                if prev_info.get("converged"):
                    unconverge_events.append({
                        "dim": dim,
                        "step": i + 1,
                    })

    return {
        "converge_events": converge_events,
        "unconverge_events": unconverge_events,
        "score_trajectory": score_trajectory,
    }


# ===== 图表 =====

def plot_convergence_timeline(project: str, log: list[dict]):
    """维度收敛堆叠面积图"""
    if not log:
        print(f"  {project}: 无日志，跳过")
        return

    fig, ax = plt.subplots(figsize=(12, 5))

    dims_order = list(DIMS_LABEL.keys())
    steps = list(range(1, len(log) + 1))

    # 每个维度：每个时间点的收敛状态 (1=converged, 0=divergent)
    converged_data = {}
    for dim in dims_order:
        converged_data[dim] = []
        for record in log:
            di = record.get("dimensions", {}).get(dim, {})
            converged_data[dim].append(1 if di.get("converged") else 0)

    # 堆叠面积图
    base = np.zeros(len(steps))
    colors = plt.cm.tab10(np.linspace(0, 1, len(dims_order)))

    for dim, color in zip(dims_order, colors):
        vals = np.array(converged_data[dim])
        label = DIMS_LABEL.get(dim, dim)
        ax.fill_between(steps, base, base + vals, label=label, color=color, alpha=0.7, step="mid")
        base += vals

    ax.set_xlabel("选择次数")
    ax.set_ylabel("收敛维度数")
    ax.set_title(f"维度收敛时间线 — {project}", fontsize=13)
    ax.set_ylim(0, len(dims_order))
    ax.set_yticks(range(0, len(dims_order) + 1, 2))
    ax.legend(loc="upper left", fontsize=8, ncol=2)
    ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    path = FIGURES_DIR / f"persona_convergence_{project}.svg"
    plt.savefig(path, format="svg")
    plt.close()
    print(f"  收敛时间线: {path.name}")


def plot_score_trajectory(project: str, trajectory: dict):
    """各维度 A/B 分数演化"""
    if not trajectory:
        return

    # 每个维度一个子图
    dims = list(trajectory.keys())
    n = len(dims)
    cols = 2
    rows = (n + cols - 1) // cols

    fig, axes = plt.subplots(rows, cols, figsize=(14, 3.5 * rows))
    axes = axes.flatten() if n > 1 else [axes]

    for ax, dim in zip(axes, dims):
        data = trajectory[dim]
        steps = [d["step"] for d in data]
        ax.plot(steps, [d["a"] for d in data], "o-", label="A (稳健派)", color="#e24a4a", markersize=3, linewidth=1)
        ax.plot(steps, [d["b"] for d in data], "s--", label="B (现代派)", color="#4a90e2", markersize=3, linewidth=1)

        # 收敛标记
        for d in data:
            if d["converged"]:
                ax.axvline(x=d["step"], color="green", alpha=0.3, linewidth=1, linestyle=":")
                break

        ax.set_title(DIMS_LABEL.get(dim, dim), fontsize=10)
        ax.set_ylabel("分数 (1~5)")
        ax.set_ylim(0.5, 5.5)
        ax.legend(fontsize=7)
        ax.grid(alpha=0.2)

    # 隐藏多余子图
    for ax in axes[n:]:
        ax.set_visible(False)

    fig.suptitle(f"A/B 分数演化 — {project}", fontsize=13, y=1.02)
    plt.tight_layout()
    path = FIGURES_DIR / f"persona_scores_{project}.svg"
    plt.savefig(path, format="svg")
    plt.close()
    print(f"  分数演化: {path.name}")


def plot_all_projects_summary(summaries: list[dict]):
    """跨项目对比柱状图"""
    if len(summaries) <= 1:
        return

    fig, axes = plt.subplots(1, 3, figsize=(14, 4))

    names = [s["project"][:12] for s in summaries]
    x = np.arange(len(names))

    ax = axes[0]
    rates = [s["convergence_rate"] * 100 for s in summaries]
    bars = ax.bar(x, rates, color="#4a90e2")
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=30, ha="right", fontsize=9)
    ax.set_ylabel("收敛率 (%)")
    ax.set_title("各项目收敛率")
    ax.set_ylim(0, 105)
    for bar, val in zip(bars, rates):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1, f"{val:.0f}%", ha="center", fontsize=8)

    ax = axes[1]
    gaps = [s["avg_a_b_gap"] for s in summaries]
    bars = ax.bar(x, gaps, color="#e24a4a")
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=30, ha="right", fontsize=9)
    ax.set_ylabel("A/B 平均差距")
    ax.set_title("各维度平均 A/B 差距")
    for bar, val in zip(bars, gaps):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02, f"{val:.2f}", ha="center", fontsize=8)

    ax = axes[2]
    conv = [s["converged_dims"] for s in summaries]
    total = [s["total_dims"] for s in summaries]
    bars = ax.bar(x, conv, label="已收敛", color="#7ecf7e")
    ax.bar(x, [t - c for t, c in zip(total, conv)], bottom=conv, label="未收敛", color="#d3d3d3")
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=30, ha="right", fontsize=9)
    ax.set_ylabel("维度数")
    ax.set_title("收敛维度分布")
    ax.legend(fontsize=8)

    plt.tight_layout()
    path = FIGURES_DIR / "persona_all_projects.svg"
    plt.savefig(path, format="svg")
    plt.close()
    print(f"  跨项目对比: {path.name}")


# ===== 主流程 =====

def main():
    print("=" * 60)
    print("  Persona 系统分析")
    print("=" * 60)
    print()

    projects = find_projects()
    if not projects:
        print("  未找到 persona state 文件")
        sys.exit(0)

    print(f"  发现 {len(projects)} 个项目: {', '.join(projects)}")
    print()

    all_summaries = []
    converge_total = 0
    unconverge_total = 0

    for project in projects:
        state = load_current_state(project)
        if not state:
            print(f"  [{project}] 状态文件无效，跳过")
            continue

        log = load_state_log(project)

        # 当前状态摘要
        summary = analyze_state_summary(project, state)
        all_summaries.append(summary)
        print(f"  [{project}]")
        print(f"    收敛: {summary['converged_dims']}/{summary['total_dims']} 维度 ({summary['convergence_rate']:.0%})")
        print(f"    A/B 平均差距: {summary['avg_a_b_gap']:.3f}")
        print(f"    全部收敛: {summary['all_converged']}")

        # 日志时间线分析
        tl = analyze_log_timeline(project, log)
        converge_total += len(tl["converge_events"])
        unconverge_total += len(tl["unconverge_events"])

        if tl["converge_events"]:
            print(f"    收敛事件: {len(tl['converge_events'])}")
            for ev in tl["converge_events"][-3:]:
                print(f"      · {DIMS_LABEL.get(ev['dim'], ev['dim'])} (第{ev['step']}步, 偏好={ev['preferred_side']})")

        if tl["unconverge_events"]:
            print(f"    衰减事件: {len(tl['unconverge_events'])}")
            for ev in tl["unconverge_events"]:
                print(f"      · {DIMS_LABEL.get(ev['dim'], ev['dim'])} (第{ev['step']}步)")

        # 图表
        if log:
            plot_convergence_timeline(project, log)
            plot_score_trajectory(project, tl["score_trajectory"])

        # 当前状态的维度详情
        dims = state.get("dimensions", {})
        a_scores = state.get("persona_a", {}).get("scores", {})
        b_scores = state.get("persona_b", {}).get("scores", {})
        converged_list = [d for d, info in dims.items() if info.get("converged")]
        divergent_list = [d for d, info in dims.items() if not info.get("converged")]

        if converged_list:
            print(f"    已收敛维度: {', '.join(DIMS_LABEL.get(d, d) for d in converged_list)}")
        if divergent_list:
            print(f"    未收敛维度: {', '.join(DIMS_LABEL.get(d, d) for d in divergent_list)}")
        print()

    # 跨项目图表
    if len(projects) > 1:
        plot_all_projects_summary(all_summaries)

    # 汇总
    print("─" * 60)
    print("  汇总")
    print("─" * 60)
    print(f"  项目数: {len(projects)}")
    avg_rate = np.mean([s["convergence_rate"] for s in all_summaries])
    print(f"  平均收敛率: {avg_rate:.1%}")
    print(f"  总收敛事件: {converge_total}")
    print(f"  总衰减事件: {unconverge_total}")
    print()
    print(f"  图表已保存到: {FIGURES_DIR}/")
    print()


if __name__ == "__main__":
    main()
