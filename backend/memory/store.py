"""
记忆存储

纯内存实现，无持久化。进程重启即清空。
支持增/删/查/向量检索。
"""

import uuid

from memory.types import MemoryItem, MemoryType
from vector_utils import cosine_similarity, embed_text


class MemoryStore:
    """
    记忆存储

    全部条目在内存中维护，不写入磁盘。
    embedding 向量按需从 deepseek 计算。
    """

    def __init__(self, project_name: str = "default"):
        self.project_name = project_name
        self.items: list[MemoryItem] = []
        self._embeddings: list[list[float]] = []

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

    def clear(self):
        """清空所有记忆（内存中）"""
        self.items = []
        self._embeddings = []
