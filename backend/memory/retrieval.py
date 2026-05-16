"""
汇聚式检索管线

参考 RagFlow Convergent Context Engine：

1. Query 改写 — 关键词扩展
2. 双路召回 — 稠密 (embedding) + 稀疏 (关键词)
3. RRF 融合 — Reciprocal Rank Fusion
4. 重排 — 按融合分数排序
5. 注入 — 格式化为 LLM 上下文
"""

import re

from memory.store import MemoryStore
from memory.types import MemoryItem, RetrievalResult

# 英文停用词（简单版本）
_STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "can", "shall",
    "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "through", "during", "before", "after",
    "above", "below", "between", "out", "off", "over", "under",
    "again", "further", "then", "once", "here", "there",
    "when", "where", "why", "how", "all", "each", "every",
    "both", "few", "more", "most", "other", "some", "such",
    "no", "nor", "not", "only", "own", "same", "so", "than",
    "too", "very", "just", "because", "but", "and", "or", "if",
    "while", "about", "up",
}


def _tokenize(text: str) -> list[str]:
    """分词 + 去停用词"""
    # 中英文分词：英文按空格，中文按字（简单处理）
    text = text.lower()
    # 提取英文单词
    words = re.findall(r"[a-z]+|\w", text)
    return [w for w in words if w not in _STOP_WORDS and len(w) > 1]


def _expand_query(query: str) -> list[str]:
    """
    Query 改写 — 关键词扩展

    简单同义词/相关词扩展，不调用 LLM（避免成本）。
    """
    expanded = [query]

    # 提取关键术语
    tokens = _tokenize(query)

    # 添加英文关键词（如果原问题是中文）
    en_tokens = [t for t in tokens if t.isascii() and t.isalpha()]
    if en_tokens:
        expanded.append(" ".join(en_tokens))

    return expanded


def retrieve(
    store: MemoryStore,
    query: str,
    top_k: int = 5,
    min_score: float = 0.1,
) -> list[RetrievalResult]:
    """
    汇聚式检索

    Args:
        store: MemoryStore 实例
        query: 用户问题
        top_k: 最终返回数量
        min_score: 最低分数阈值

    Returns:
        按融合分数排序的检索结果
    """
    if store.count() == 0:
        return []

    # Stage 1: Query 改写
    queries = _expand_query(query)
    keywords = list(set(_tokenize(query)))  # 去重关键词

    # Stage 2: 双路召回
    dense_results: list[tuple[MemoryItem, float, str]] = []
    sparse_results: list[tuple[MemoryItem, float, str]] = []

    for q in queries:
        items_scores = store.search(q, top_k=top_k * 2)
        for item, score in items_scores:
            if score >= min_score:
                dense_results.append((item, score, "dense"))

    # 稀疏检索
    if keywords:
        items_scores = store.search_sparse(keywords, top_k=top_k * 2)
        for item, score in items_scores:
            if score >= min_score * 0.5:
                sparse_results.append((item, score, "sparse"))

    # Stage 3: RRF 融合
    seen: dict[str, dict] = {}  # item_id -> {item, dense_rank, sparse_rank}

    for rank, (item, score, source) in enumerate(dense_results):
        if item.id not in seen:
            seen[item.id] = {"item": item, "dense_rank": None, "sparse_rank": None}
        if seen[item.id]["dense_rank"] is None:
            seen[item.id]["dense_rank"] = rank + 1

    for rank, (item, score, source) in enumerate(sparse_results):
        if item.id not in seen:
            seen[item.id] = {"item": item, "dense_rank": None, "sparse_rank": None}
        if seen[item.id]["sparse_rank"] is None:
            seen[item.id]["sparse_rank"] = rank + 1

    # RRF 分数 = 1/(rank + K)
    K = 60
    scored_results = []
    for item_id, data in seen.items():
        rrf_score = 0.0
        if data["dense_rank"] is not None:
            rrf_score += 1.0 / (data["dense_rank"] + K)
        if data["sparse_rank"] is not None:
            rrf_score += 1.0 / (data["sparse_rank"] + K)
        scored_results.append((data["item"], rrf_score))

    # 排序
    scored_results.sort(key=lambda x: x[1], reverse=True)

    # 构建结果
    results = []
    for rank, (item, score) in enumerate(scored_results[:top_k]):
        results.append(RetrievalResult(
            item=item,
            score=score,
            rank=rank + 1,
            source="fusion",
        ))

    return results


def format_context(results: list[RetrievalResult]) -> str:
    """
    将检索结果格式化为 LLM 上下文

    按类型分组展示，分别注入。
    """
    if not results:
        return ""

    semantic_items = []
    episodic_items = []
    procedural_items = []

    for r in results:
        if r.item.type == "semantic":
            semantic_items.append(r)
        elif r.item.type == "episodic":
            episodic_items.append(r)
        else:
            procedural_items.append(r)

    parts = []

    if semantic_items:
        parts.append("## 关于你和你的项目（长期记忆）")
        for r in semantic_items:
            parts.append(f"- {r.item.content}")
        parts.append("")

    if episodic_items:
        parts.append("## 最近的对话（短期记忆）")
        for r in episodic_items:
            parts.append(r.to_context())
        parts.append("")

    if procedural_items:
        parts.append("## 你的偏好模式")
        for r in procedural_items:
            parts.append(f"- {r.item.content}")
        parts.append("")

    return "\n".join(parts)
