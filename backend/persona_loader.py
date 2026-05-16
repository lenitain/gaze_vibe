"""
Persona 加载器

从 backend/personas/ 目录加载 YAML 定义，生成 system prompt。

用法:
    persona = PersonaLoader.load("稳健派")
    prompt = persona.build_system_prompt()

    # 列出所有可用 Persona
    names = PersonaLoader.list_personas()
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml

_PERSONAS_DIR = Path(__file__).parent / "personas"

# 维度描述文本
DIMENSION_DESCRIPTIONS: dict[str, dict[int, str]] = {
    "ecosystem_maturity": {
        1: "敢于使用 0.x 新产品",
        2: "愿意尝试较新的工具",
        3: "偏好中等成熟度的方案",
        4: "倾向选择久经考验的方案",
        5: "只看 star >10k、维护 >3 年的",
    },
    "correctness_strategy": {
        1: "完全信赖运行时检查 + 测试覆盖",
        2: "编译器辅助为主，但不迷信类型",
        3: "类型系统和测试并重",
        4: "倾向类型系统约束",
        5: "类型系统约束 + 编译期保证",
    },
    "naming_style": {
        1: "短名优先（ret, val, ok）",
        2: "偏短，类型完备即可",
        3: "适度语义化",
        4: "语义化命名，长一点没关系",
        5: "极端语义化长名（retrieved_data）",
    },
    "documentation_depth": {
        1: "类型即文档",
        2: "公共 API 简要说明",
        3: "关键函数有注释",
        4: "公共 API 必有 doc + 示例",
        5: "每个函数都有完整文档",
    },
    "error_handling": {
        1: "anyhow / 早 return",
        2: "anyhow + ? 操作符",
        3: "混合使用简单错误和自定义类型",
        4: "自定义错误类型为主",
        5: "自定义错误类型 / 显式 match",
    },
    "edge_case_coverage": {
        1: "关注主流路径，极端忽略",
        2: "核心路径覆盖边界",
        3: "常见边界有处理",
        4: "大部分边界已处理",
        5: "每个非法输入都有处理",
    },
    "dependency_philosophy": {
        1: "能加就加，不造轮子",
        2: "合理使用第三方库",
        3: "有选择地加依赖",
        4: "每加一个依赖都认真考虑",
        5: "自包含优先，每加依赖都斟酌",
    },
    "abstraction_timing": {
        1: "DRY 驱动，出现重复即抽象",
        2: "两次重复就抽象",
        3: "三次重复再抽象",
        4: "等重复多次再抽象",
        5: "等重复 3 次以上再抽象",
    },
    "testing_strategy": {
        1: "集成测试为主",
        2: "集成测试 + property-based",
        3: "单元测试 + 集成测试",
        4: "较高单元测试覆盖",
        5: "单元测试全覆盖 + 每个分支",
    },
    "performance_priority": {
        1: "先写对人可读的",
        2: "可读性优先，有需要再优化",
        3: "适当考虑性能",
        4: "设计时考虑性能",
        5: "设计时考虑性能，选型看 benchmark",
    },
}

# 维度优先级排序（经验权重越高 -> 优先级越高）
DIMENSION_PRIORITY = [
    "ecosystem_maturity",
    "correctness_strategy",
    "error_handling",
    "edge_case_coverage",
    "testing_strategy",
    "dependency_philosophy",
    "naming_style",
    "documentation_depth",
    "abstraction_timing",
    "performance_priority",
]


@dataclass
class AnchorDecision:
    """锚定决策"""
    domain: str
    context: str
    choice: str
    reasoning: str


@dataclass
class Persona:
    """Persona 定义"""
    name: str
    identity: str
    scores: dict[str, int] = field(default_factory=dict)
    anchor_decisions: list[AnchorDecision] = field(default_factory=list)

    def build_system_prompt(self, include_anchors: bool = True) -> str:
        """
        从 Persona 定义动态生成 system prompt
        """
        parts = [self.identity.strip(), ""]

        # 价值观（按优先级排列）
        parts.append("你的价值观（按优先级从高到低）：")
        for dim in DIMENSION_PRIORITY:
            score = self.scores.get(dim, 3.0)
            int_score = round(score)
            desc = DIMENSION_DESCRIPTIONS.get(dim, {}).get(int_score, "")
            label = DIMENSION_LABELS.get(dim, dim)
            parts.append(f"{DIMENSION_PRIORITY.index(dim) + 1}. {label} ({score:.1f}/5) — {desc}")

        parts.append("")

        # 锚定决策
        if include_anchors and self.anchor_decisions:
            parts.append("你在以下场景的决策偏好（供参考，不是硬约束）：")
            for ad in self.anchor_decisions:
                parts.append(f"- {ad.domain}: {ad.choice}")
                parts.append(f"  · {ad.context} → {ad.reasoning}")

        parts.append("")
        parts.append(
            "在回答用户问题时，保持这种一惯性。\n"
            "如果你的建议和用户已有的依赖/设计冲突，简要说明理由。"
        )

        return "\n".join(parts)


# 维度中文标签
DIMENSION_LABELS = {
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


class PersonaLoader:
    """Persona 加载器"""

    @staticmethod
    def load(name: str) -> Persona:
        """
        按名称加载 Persona

        Args:
            name: Persona 名称（如 "稳健派"），或文件名（含/不含 .yaml 后缀）

        Returns:
            Persona 对象
        """
        # 尝试多种路径
        candidates = [
            _PERSONAS_DIR / f"{name}.yaml",
            _PERSONAS_DIR / f"{name}.yml",
            _PERSONAS_DIR / name,
            _PERSONAS_DIR / f"{name}.yaml",
        ]

        filepath = None
        for p in candidates:
            if p.exists() and p.is_file():
                filepath = p
                break

        if filepath is None:
            raise FileNotFoundError(
                f"Persona 文件不存在: {name} (查找路径: {_PERSONAS_DIR})"
            )

        return PersonaLoader._load_file(filepath)

    @staticmethod
    def _load_file(filepath: Path) -> Persona:
        """从 YAML 文件加载 Persona"""
        raw = filepath.read_text(encoding="utf-8")
        data = yaml.safe_load(raw)

        anchor_decisions = []
        for ad in data.get("anchor_decisions", []):
            anchor_decisions.append(
                AnchorDecision(
                    domain=ad["domain"],
                    context=ad["context"],
                    choice=ad["choice"],
                    reasoning=ad["reasoning"],
                )
            )

        return Persona(
            name=data["name"],
            identity=data["identity"],
            scores=data.get("scores", {}),
            anchor_decisions=anchor_decisions,
        )

    @staticmethod
    def list_personas() -> list[str]:
        """列出所有可用 Persona 名称"""
        personas = []
        for fpath in sorted(_PERSONAS_DIR.glob("*.yaml")):
            data = yaml.safe_load(fpath.read_text(encoding="utf-8"))
            personas.append(data.get("name", fpath.stem))
        return personas

    @staticmethod
    def get_persona_bias_value(persona: Persona) -> float:
        """
        将 Persona 映射到 0~1 的单维度值

        0.0 = 绝对现代派, 1.0 = 绝对稳健派
        基于关键维度的加权平均。
        """
        # 影响"人格派系"的关键维度及其权重
        key_dims = {
            "ecosystem_maturity": 0.25,
            "correctness_strategy": 0.20,
            "error_handling": 0.15,
            "edge_case_coverage": 0.15,
            "dependency_philosophy": 0.15,
            "testing_strategy": 0.10,
        }

        weighted_sum = 0.0
        total_weight = 0.0
        for dim, weight in key_dims.items():
            score = persona.scores.get(dim, 3)
            # 1~5 映射到 0~1
            normalized = (score - 1) / 4.0
            weighted_sum += normalized * weight
            total_weight += weight

        if total_weight == 0:
            return 0.5

        return weighted_sum / total_weight
