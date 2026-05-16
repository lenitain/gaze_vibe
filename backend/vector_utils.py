"""
向量工具 — Embedding + 相似度计算

复用 DeepSeek API（兼容 OpenAI embedding 端点），纯 Python 实现 cosine similarity。
"""

import numpy as np

from config import EMBEDDING_MODEL

# 全局 embedding client，由 app.py 在初始化时设置
_embed_client = None


def init_embedding_client(client):
    """初始化 embedding 客户端（由 app.py 调用）"""
    global _embed_client
    _embed_client = client


def embed_text(text: str) -> list[float]:
    """将文本转为 embedding 向量"""
    if _embed_client is None:
        raise RuntimeError("embedding client 未初始化，请先调用 init_embedding_client()")

    response = _embed_client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text,
    )
    return response.data[0].embedding


def embed_batch(texts: list[str]) -> list[list[float]]:
    """批量 embedding"""
    if not texts:
        return []
    if _embed_client is None:
        raise RuntimeError("embedding client 未初始化")

    response = _embed_client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
    )
    sorted_data = sorted(response.data, key=lambda x: x.index)
    return [item.embedding for item in sorted_data]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """余弦相似度"""
    vec_a = np.array(a, dtype=np.float64)
    vec_b = np.array(b, dtype=np.float64)
    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(vec_a, vec_b) / (norm_a * norm_b))


def compute_similarity_matrix(queries: list[list[float]], candidates: list[list[float]]) -> np.ndarray:
    """批量计算相似度矩阵 (n_queries × n_candidates)"""
    q = np.array(queries, dtype=np.float64)
    c = np.array(candidates, dtype=np.float64)
    q_norm = q / np.linalg.norm(q, axis=1, keepdims=True)
    c_norm = c / np.linalg.norm(c, axis=1, keepdims=True)
    return np.dot(q_norm, c_norm.T)
