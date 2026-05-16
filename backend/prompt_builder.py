"""
动态 System Prompt 组装器

替代当前 adjust_system_prompt() 手写拼接的方式，
用链式调用组装 prompt 组件：

    prompt = PromptBuilder("system_a") \\
        .with_eye_adjustment(detail_score=0.72, explanation_score=0.64) \\
        .with_context(files) \\
        .with_additional_notes(["用户是 Python 开发者", "关注性能"]) \\
        .build()
"""

from dataclasses import dataclass, field

from prompts import load_prompt


@dataclass
class PromptComponent:
    """一个 prompt 组件"""
    key: str
    content: str
    weight: float = 1.0  # 排序权重，越大越靠后


class PromptBuilder:
    """
    链式 prompt 组装器

    每个 .with_*() 方法添加一个组件，build() 时按 weight 排序组装。
    base_name 指向 prompts/ 目录下的 .md 文件（不含后缀）。
    """

    def __init__(self, base_name: str):
        self.base_name = base_name
        self.components: list[PromptComponent] = []

        # 额外的说明（自由的文本块）
        self.additional_notes: list[str] = []

    # ----- 眼动调整 -----

    def with_eye_adjustment(
        self,
        detail_score: float = 0.5,
        explanation_score: float = 0.5,
        confidence: float | None = None,
    ) -> "PromptBuilder":
        """
        添加眼动偏好调整块

        根据 detail_score 和 explanation_score 生成自然语言指令，
        插入到 base prompt 之前。
        """
        notes: list[str] = []

        if detail_score > 0.55:
            strength = "更" if detail_score < 0.65 else "明显"
            notes.append(f"用户偏好详细解答，请提供{strength}完整的解释和示例")
        elif detail_score < 0.45:
            strength = "更" if detail_score > 0.35 else "明显"
            notes.append(f"用户偏好简洁解答，请{strength}精简解释，直接给核心代码")

        if explanation_score > 0.55:
            strength = "适当" if explanation_score < 0.65 else "多"
            notes.append(f"用户喜欢原理性解释，请{strength}增加设计思路和原理解释")
        elif explanation_score < 0.45:
            strength = "适当" if explanation_score > 0.35 else "尽量"
            notes.append(f"用户喜欢直接看代码，请{strength}减少文字解释，代码优先")

        if confidence is not None and confidence >= 0.8:
            notes.append(f"模型置信度较高 ({confidence:.0%})，请优先遵循上述调整")

        if not notes:
            return self

        content = "\n\n[用户偏好调整]\n" + "\n".join(f"- {note}" for note in notes)
        self.components.append(PromptComponent(key="eye_adjustment", content=content, weight=0.3))
        return self

    # ----- 项目文件上下文 -----

    def with_context(self, context_files: list[dict] | None) -> "PromptBuilder":
        """
        添加项目文件上下文块
        """
        if not context_files:
            return self

        parts = ["\n\n## 项目文件上下文\n\n"]
        for file in context_files:
            lang = file.get("lang", "")
            parts.append(f"### {file['path']}\n\n```{lang}\n{file['content']}\n```\n\n")
        parts.append("请基于以上项目代码上下文回答用户的问题。\n")

        content = "".join(parts)
        self.components.append(PromptComponent(key="context", content=content, weight=0.6))
        return self

    # ----- 对话历史 -----

    def with_history(self, history: list[dict] | None) -> "PromptBuilder":
        """
        添加对话历史摘要

        history 格式: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
        """
        if not history:
            return self

        parts = ["\n\n## 对话历史\n\n"]
        for msg in history[-4:]:  # 最多 4 条
            role = "用户" if msg["role"] == "user" else "助手"
            content = msg["content"][:200]
            parts.append(f"**{role}**: {content}\n\n")

        content = "".join(parts)
        self.components.append(PromptComponent(key="history", content=content, weight=0.4))
        return self

    # ----- 自由说明 -----

    def with_note(self, note: str) -> "PromptBuilder":
        """添加一条自由说明"""
        self.additional_notes.append(note)
        return self

    # ----- 结构化输出指令 -----

    def with_output_schema(self, schema_description: str) -> "PromptBuilder":
        """
        添加结构化输出指令

        当使用 function calling 时，model 不需要看到 schema 定义（由 API 参数传递）。
        但添加提示有助于 model 生成更符合预期的内容。
        """
        self.additional_notes.append(f"\n请按照以下结构组织输出:\n{schema_description}")
        return self

    # ----- 构建最终 prompt -----

    def build(self) -> str:
        """
        按 weight 排序组装所有组件

        组装顺序:
        1. base prompt (weight=0) — 从 prompts/ 加载
        2. eye adjustment (weight=0.3) — 眼动偏好
        3. history (weight=0.4) — 对话历史
        4. context (weight=0.6) — 项目上下文
        5. additional notes (weight=1.0) — 自由说明
        """
        base = load_prompt(self.base_name)

        # 按 weight 排序
        sorted_comps = sorted(self.components, key=lambda c: c.weight)

        parts = [base]
        for comp in sorted_comps:
            parts.append(comp.content)

        if self.additional_notes:
            parts.append("\n\n[附加说明]\n" + "\n".join(f"- {note}" for note in self.additional_notes))

        return "".join(parts)

    def build_dual(self) -> tuple[str, str]:
        """
        同时构建 A/B 两个 prompt

        返回 (prompt_a, prompt_b)
        """
        # 额外说明在两个 prompt 中都保留
        extra_components = [c for c in self.components if c.key not in ("eye_adjustment",)]

        # A: 详细
        prompt_a = self.base_name + "_a" if self.base_name == "system" else self.base_name
        if not self.base_name.endswith("_a"):
            prompt_a = self.base_name

        # B: 简洁
        prompt_b = self.base_name + "_b" if self.base_name == "system" else self.base_name
        if not self.base_name.endswith("_b"):
            prompt_b = self.base_name

        return (prompt_a, prompt_b)


# ===== 便捷工厂函数 =====

def build_answer_prompt(
    style: str,
    detail_score: float = 0.5,
    explanation_score: float = 0.5,
    confidence: float | None = None,
    context_files: list[dict] | None = None,
    history: list[dict] | None = None,
    notes: list[str] | None = None,
) -> str:
    """
    一键构建答案 prompt

    Args:
        style: "detailed" 或 "concise"
        detail_score: 眼动详细程度分数
        explanation_score: 眼动解释程度分数
        confidence: 置信度
        context_files: 项目文件上下文
        history: 对话历史
        notes: 额外的自由说明
    """
    base = "system_a" if style == "detailed" else "system_b"
    builder = PromptBuilder(base)

    if detail_score != 0.5 or explanation_score != 0.5:
        builder.with_eye_adjustment(detail_score, explanation_score, confidence)
    if context_files:
        builder.with_context(context_files)
    if history:
        builder.with_history(history)
    if notes:
        for note in notes:
            builder.with_note(note)

    return builder.build()


def build_dual_answer_prompts(
    detail_score: float = 0.5,
    explanation_score: float = 0.5,
    confidence: float | None = None,
    context_files: list[dict] | None = None,
    history: list[dict] | None = None,
) -> tuple[str, str]:
    """
    同时构建 A/B 两个 prompt

    Returns:
        (prompt_a, prompt_b)
    """
    prompt_a = build_answer_prompt("detailed", detail_score, explanation_score, confidence, context_files, history)
    prompt_b = build_answer_prompt("concise", detail_score, explanation_score, confidence, context_files, history)
    return prompt_a, prompt_b
