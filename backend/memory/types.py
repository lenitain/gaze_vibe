"""
记忆系统数据类型

三层记忆模型（参考 RagFlow）：
- semantic: 用户项目的长期事实（技术栈、约束等）
- episodic: 会话事件（提问→回答→选择）
- procedural: 跨会话的隐性偏好模式
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

MemoryType = Literal["semantic", "episodic", "procedural"]


@dataclass
class MemoryItem:
    """一条记忆条目"""
    id: str
    type: MemoryType
    content: str
    source_query: str = ""
    persona: str | None = None
    created_at: str = ""
    invalid_at: str | None = None
    confidence: float = 1.0
    embedding: list[float] | None = None
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    @property
    def is_valid(self) -> bool:
        if self.invalid_at:
            return datetime.now().isoformat() < self.invalid_at
        return True


@dataclass
class RetrievalResult:
    """检索结果"""
    item: MemoryItem
    score: float
    rank: int = 0
    source: str = "dense"  # dense / sparse

    def to_context(self) -> str:
        """转成 LLM 可见的上下文文本"""
        lines = [f"[{self.item.type}] {self.item.content}"]
        if self.item.source_query:
            lines.append(f"  来源问题: {self.item.source_query}")
        if self.item.persona:
            lines.append(f"  相关 Persona: {self.item.persona}")
        if self.item.confidence < 1.0:
            lines.append(f"  置信度: {self.item.confidence:.2f}")
        return "\n".join(lines)
