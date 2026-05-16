"""
记忆存储

内存 numpy 矩阵 + JSONL 持久化，轻量无外部依赖。
支持增/删/查/向量检索。
"""

import json
import uuid
from datetime import datetime
from pathlib import Path

from memory.types import MemoryItem, MemoryType
from vector_utils import cosine_similarity, embed_text

DATA_DIR = Path(__file__).parent.parent / "memory_data"


class MemoryStore:
    """
    记忆存储

    全部条目在内存中维护，同步持久化到 JSONL。
    embedding 向量存在 numpy 矩阵中，按需从 deepseek 计算。
    """

    def __init__(self, data_dir: str | Path = DATA_DIR):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.items: list[MemoryItem] = []
        self._embeddings: list[list[float]] = []  # 与 items 一一对应

        self._load()

    # ===== 写 =====

    def add(self, item: MemoryItem) -> str:
        """添加一条记忆，返回 ID"""
        if not item.id:
            item.id = str(uuid.uuid4())
        if not item.created_at:
            item.created_at = datetime.now().isoformat()

        # 计算 embedding
        if not item.embedding:
            try:
                item.embedding = embed_text(item.content)
            except Exception as e:
                print(f"  [Memory] embedding 失败: {e}")
                item.embedding = []

        self.items.append(item)
        self._embeddings.append(item.embedding or [])

        self._append_item(item)
        return item.id

    def add_episodic(
        self,
        content: str,
        source_query: str = "",
        persona: str | None = None,
        confidence: float = 1.0,
        metadata: dict | None = None,
    ) -> str:
        """快速添加 episodic 记忆"""
        return self.add(MemoryItem(
            id="",
            type="episodic",
            content=content,
            source_query=source_query,
            persona=persona,
            confidence=confidence,
            metadata=metadata or {},
        ))

    def add_semantic(
        self,
        content: str,
        source_query: str = "",
        confidence: float = 1.0,
        metadata: dict | None = None,
    ) -> str:
        """快速添加 semantic 记忆"""
        return self.add(MemoryItem(
            id="",
            type="semantic",
            content=content,
            source_query=source_query,
            confidence=confidence,
            metadata=metadata or {},
        ))

    def invalidate(self, item_id: str):
        """标记记忆为过期"""
        for item in self.items:
            if item.id == item_id:
                item.invalid_at = datetime.now().isoformat()
                break

    # ===== 读 =====

    def get(self, item_id: str) -> MemoryItem | None:
        """按 ID 获取记忆"""
        for item in self.items:
            if item.id == item_id:
                return item
        return None

    def get_all(self, type_filter: MemoryType | None = None) -> list[MemoryItem]:
        """获取全部（可选按类型过滤）"""
        if type_filter:
            return [i for i in self.items if i.type == type_filter and i.is_valid]
        return [i for i in self.items if i.is_valid]

    def get_recent(self, n: int = 5, type_filter: MemoryType | None = None) -> list[MemoryItem]:
        """获取最近 n 条"""
        items = self.get_all(type_filter)
        items.sort(key=lambda x: x.created_at, reverse=True)
        return items[:n]

    # ===== 向量检索 =====

    def search(self, query: str, top_k: int = 5) -> list[tuple[MemoryItem, float]]:
        """
        向量检索最相似的记忆

        Args:
            query: 查询文本
            top_k: 返回数量

        Returns:
            [(item, similarity_score), ...]
        """
        valid_indices = [i for i, item in enumerate(self.items) if item.is_valid and self._embeddings[i]]
        if not valid_indices:
            return []

        try:
            query_vec = embed_text(query)
        except Exception as e:
            print(f"  [Memory] 查询 embedding 失败: {e}")
            return []

        scores = []
        for idx in valid_indices:
            score = cosine_similarity(query_vec, self._embeddings[idx])
            scores.append((idx, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return [(self.items[idx], score) for idx, score in scores[:top_k]]

    def search_sparse(self, keywords: list[str], top_k: int = 5) -> list[tuple[MemoryItem, float]]:
        """
        关键词检索（BM25 近似）
        作为稠密检索的补充
        """
        valid_items = [(i, item) for i, item in enumerate(self.items) if item.is_valid]
        if not valid_items:
            return []

        scored = []
        for idx, item in valid_items:
            score = 0.0
            content_lower = item.content.lower()
            for kw in keywords:
                kw_lower = kw.lower()
                count = content_lower.count(kw_lower)
                if count > 0:
                    # 简单 TF 近似
                    score += count / (len(content_lower.split()) + 1)
            if score > 0:
                scored.append((idx, item, score))

        scored.sort(key=lambda x: x[2], reverse=True)
        return [(item, score) for _, item, score in scored[:top_k]]

    # ===== 统计 =====

    def count(self, type_filter: MemoryType | None = None) -> int:
        return len(self.get_all(type_filter))

    # ===== 持久化 =====

    def _append_item(self, item: MemoryItem):
        """追加一条记录到 JSONL"""
        path = self.data_dir / "items.jsonl"
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(self._item_to_dict(item), ensure_ascii=False) + "\n")

    def _load(self):
        """从 JSONL 恢复"""
        path = self.data_dir / "items.jsonl"
        if not path.exists():
            return

        self.items = []
        self._embeddings = []

        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    item = self._dict_to_item(data)
                    self.items.append(item)
                    self._embeddings.append(item.embedding or [])
                except Exception as e:
                    print(f"  [Memory] 加载条目失败: {e}")

    def clear(self):
        """清空所有记忆"""
        self.items = []
        self._embeddings = []
        for f in self.data_dir.glob("*"):
            f.unlink()

    @staticmethod
    def _item_to_dict(item: MemoryItem) -> dict:
        return {
            "id": item.id,
            "type": item.type,
            "content": item.content,
            "source_query": item.source_query,
            "persona": item.persona,
            "created_at": item.created_at,
            "invalid_at": item.invalid_at,
            "confidence": item.confidence,
            "embedding": item.embedding,
            "metadata": item.metadata,
        }

    @staticmethod
    def _dict_to_item(data: dict) -> MemoryItem:
        return MemoryItem(
            id=data["id"],
            type=data["type"],
            content=data["content"],
            source_query=data.get("source_query", ""),
            persona=data.get("persona"),
            created_at=data.get("created_at", ""),
            invalid_at=data.get("invalid_at"),
            confidence=data.get("confidence", 1.0),
            embedding=data.get("embedding"),
            metadata=data.get("metadata", {}),
        )
