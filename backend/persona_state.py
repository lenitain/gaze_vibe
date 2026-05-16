"""
Persona 状态持久化 + 动态调整

管理两个 Persona 当前 scores 的持久化（不在 YAML 中硬编码）。
每轮用户选择后：
- 选中侧 → 不变
- 未选中侧 → EMA 朝向选中侧收束
- 收敛后 → 未被选中的一侧随机探索
"""

import json
import random
from pathlib import Path
from typing import Optional

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

STATE_FILE = Path(__file__).parent / "persona_state.json"


class PersonaState:
    """Persona 动态状态"""

    def __init__(
        self,
        persona_a_name: str = "稳健派",
        persona_b_name: str = "现代派",
    ):
        self.persona_a_name = persona_a_name
        self.persona_b_name = persona_b_name

        # 加载初始 scores（从 YAML）
        self.persona_a: Persona = PersonaLoader.load(persona_a_name)
        self.persona_b: Persona = PersonaLoader.load(persona_b_name)

        # 将 int scores 转为 float（保留原本的值）
        for dim in self.persona_a.scores:
            self.persona_a.scores[dim] = float(self.persona_a.scores[dim])
        for dim in self.persona_b.scores:
            self.persona_b.scores[dim] = float(self.persona_b.scores[dim])

        self.converged = False

    def record_choice(self, chosen_side: str):
        """
        记录用户选择，调整 Persona scores

        Args:
            chosen_side: "A" 或 "B"
        """
        if chosen_side == "A":
            chosen_p = self.persona_a
            other_p = self.persona_b
        else:
            chosen_p = self.persona_b
            other_p = self.persona_a

        # 检测是否已收敛
        gap = self._convergence_gap()
        if gap < CONVERGE_THRESHOLD:
            self.converged = True

        if not self.converged:
            # 收敛中：未选中侧 EMA 朝向选中侧
            for dim in DIMENSION_PRIORITY:
                if dim not in chosen_p.scores or dim not in other_p.scores:
                    continue
                target = chosen_p.scores[dim]
                current = other_p.scores[dim]
                new_val = ALPHA * target + (1 - ALPHA) * current
                other_p.scores[dim] = round(new_val, 2)

                # 保持在 1-5 范围内
                other_p.scores[dim] = max(1.0, min(5.0, other_p.scores[dim]))
        else:
            # 收敛后：未被选中的一侧随机探索
            self._explore_random(other_p)

    def _convergence_gap(self) -> float:
        """计算两个 Persona 在关键维度上的平均差距"""
        gaps = []
        for dim in KEY_DIMS:
            a = self.persona_a.scores.get(dim, 3.0)
            b = self.persona_b.scores.get(dim, 3.0)
            gaps.append(abs(a - b))
        return sum(gaps) / len(gaps) if gaps else 0.0

    def _explore_random(self, persona: Persona):
        """随机探索：在 1-2 个维度上 ±1 随机扰动"""
        available_dims = [d for d in DIMENSION_PRIORITY if d in persona.scores]
        if not available_dims:
            return

        n_dims = random.randint(1, min(2, len(available_dims)))
        dims_to_change = random.sample(available_dims, n_dims)

        for dim in dims_to_change:
            delta = random.choice([-1.0, -0.5, 0.5, 1.0])
            new_val = persona.scores[dim] + delta
            persona.scores[dim] = max(1.0, min(5.0, round(new_val, 2)))

    def get_persona_bias(self) -> float:
        """
        计算当前 Persona 之间的偏差（用于前端显示）

        0.0 = 两个 Persona 完全相同
        1.0 = 两个 Persona 在关键维度上差异极大
        """
        gap = self._convergence_gap()
        # gap 范围约 0~4，归一化到 0~1
        return min(1.0, gap / 4.0)

    def save(self):
        """持久化到 JSON"""
        data = {
            "version": 1,
            "converged": self.converged,
            "persona_a": {
                "name": self.persona_a_name,
                "scores": self.persona_a.scores,
            },
            "persona_b": {
                "name": self.persona_b_name,
                "scores": self.persona_b.scores,
            },
        }
        STATE_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @classmethod
    def load_or_create(
        cls,
        persona_a_name: str = "稳健派",
        persona_b_name: str = "现代派",
    ) -> "PersonaState":
        """从持久化恢复，或创建新的状态"""
        if STATE_FILE.exists():
            try:
                data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
                state = cls(
                    persona_a_name=data["persona_a"]["name"],
                    persona_b_name=data["persona_b"]["name"],
                )
                # 恢复 scores（覆盖从 YAML 读取的初始值）
                for dim, val in data["persona_a"]["scores"].items():
                    state.persona_a.scores[dim] = val
                for dim, val in data["persona_b"]["scores"].items():
                    state.persona_b.scores[dim] = val
                state.converged = data.get("converged", False)
                return state
            except Exception:
                pass

        return cls(persona_a_name, persona_b_name)

    @classmethod
    def reset(cls):
        """重置状态文件"""
        if STATE_FILE.exists():
            STATE_FILE.unlink()
