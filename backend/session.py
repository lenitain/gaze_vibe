"""
Session 树 — 替代扁平 conversationHistory

提供树状结构的历史记录，支持分支、回溯、context 构建。
参考 pi 的 SessionTree 模式。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from storage import Storage

SessionEntryType = Literal[
    "question",          # 用户提问
    "answer_a",          # 详细解答
    "answer_b",          # 简洁解答
    "eye_data",          # 眼动数据
    "choice",            # 用户选择
    "persona_change",    # Persona 维度变化
    "tool_exec",         # 工具执行
    "system",            # 系统消息
]


@dataclass
class SessionEntry:
    """一条 Session 记录"""
    id: str = ""
    parent_id: str | None = None
    type: SessionEntryType = "system"
    timestamp: str = ""
    data: dict = field(default_factory=dict)  # 负载数据，按 type 不同结构不同

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "parentId": self.parent_id,
            "type": self.type,
            "timestamp": self.timestamp,
            "data": self.data,
        }


@dataclass
class SessionState:
    """Session 持久化状态"""
    entries: list[SessionEntry] = field(default_factory=list)
    current_leaf_id: str | None = None
    session_id: str = ""
    project_name: str = "default"
    created_at: str = ""
    updated_at: str = ""


class Session:
    """
    Session 树

    以 Storage 为后端存储会话历史。
    提供树状结构，支持分支和 context 构建。

    Usage:
        storage = MemoryStorage[SessionState]()
        session = Session(storage, "my-project")
        session.append("question", {"text": "How do I ..."})
        session.append("answer_a", {"text": "You can ..."})
        context = session.build_context()
    """

    def __init__(self, storage: Storage[SessionState], project_name: str = "default"):
        self._storage = storage
        self._project_name = project_name
        self._state: SessionState | None = None
        self._load_or_create()

    # ===== 内部 =====

    def _load_or_create(self):
        """从 Storage 加载或创建新 Session"""
        loaded = self._storage.get(self._project_name)
        if loaded is not None:
            self._state = loaded
        else:
            now = datetime.now().isoformat()
            self._state = SessionState(
                session_id=str(uuid.uuid4()),
                project_name=self._project_name,
                created_at=now,
                updated_at=now,
            )
            self._save()

    def _save(self):
        """持久化当前状态"""
        if self._state is not None:
            self._state.updated_at = datetime.now().isoformat()
            self._storage.set(self._project_name, self._state)

    # ===== 写操作 =====

    def append(
        self,
        entry_type: SessionEntryType,
        data: dict,
        parent_id: str | None = None,
    ) -> str:
        """
        追加一条 Session 记录

        Args:
            entry_type: 记录类型
            data: 负载数据
            parent_id: 父节点 ID，None 则挂到 current_leaf 下

        Returns:
            新记录的 ID
        """
        if self._state is None:
            raise RuntimeError("Session 未初始化")

        parent = parent_id or self._state.current_leaf_id

        entry = SessionEntry(
            type=entry_type,
            parent_id=parent,
            data=data,
        )
        self._state.entries.append(entry)
        self._state.current_leaf_id = entry.id
        self._save()
        return entry.id

    def get_branch(self, leaf_id: str | None = None) -> list[SessionEntry]:
        """
        从指定节点（或 current_leaf）回溯到根，返回时间正序的链

        Returns:
            [root_entry, ..., leaf_entry]
        """
        if self._state is None:
            return []

        leaf = leaf_id or self._state.current_leaf_id
        if leaf is None:
            return []

        # 构建 id → entry 索引
        entry_map = {e.id: e for e in self._state.entries}

        # 回溯
        chain: list[SessionEntry] = []
        current_id: str | None = leaf
        while current_id is not None:
            entry = entry_map.get(current_id)
            if entry is None:
                break
            chain.append(entry)
            current_id = entry.parent_id

        # 反转成时间正序
        chain.reverse()
        return chain

    def build_context(self, max_entries: int = 10) -> list[dict]:
        """
        构建 LLM 上下文

        从 current_leaf 回溯取最近 max_entries 条记录，
        返回适合注入 prompt 的 dict 列表。

        Returns:
            [{"role": "user"|"assistant"|"system", "content": str}, ...]
        """
        branch = self.get_branch()
        # 取最近 max_entries 条
        recent = branch[-max_entries:] if len(branch) > max_entries else branch

        context: list[dict] = []
        for entry in recent:
            ctx = self._entry_to_context(entry)
            if ctx:
                context.append(ctx)

        return context

    @staticmethod
    def _entry_to_context(entry: SessionEntry) -> dict | None:
        """将单条 entry 转为 LLM context dict"""
        t = entry.type
        d = entry.data

        if t == "question":
            return {"role": "user", "content": d.get("text", "")}
        elif t == "answer_a":
            return {"role": "assistant", "content": f"[详细解答]\n{d.get('text', '')}"}
        elif t == "answer_b":
            return {"role": "assistant", "content": f"[简洁解答]\n{d.get('text', '')}"}
        elif t == "choice":
            return {"role": "user", "content": f"[用户选择: {d.get('side', 'unknown')}]"}
        elif t == "persona_change":
            return {"role": "system", "content": f"[Persona 调整] {d.get('summary', '')}"}
        elif t == "eye_data":
            return None  # 眼动原始数据不注入 context
        elif t == "tool_exec":
            return {"role": "system", "content": f"[工具执行: {d.get('tool', '')}] {d.get('summary', '')}"}
        return None

    # ===== 查询 =====

    @property
    def session_id(self) -> str:
        return self._state.session_id if self._state else ""

    @property
    def entry_count(self) -> int:
        return len(self._state.entries) if self._state else 0

    def get_all_entries(self) -> list[SessionEntry]:
        return list(self._state.entries) if self._state else []

    def clear(self):
        """清空并重置 Session"""
        if self._state is not None:
            self._state.entries.clear()
            self._state.current_leaf_id = None
            self._save()
