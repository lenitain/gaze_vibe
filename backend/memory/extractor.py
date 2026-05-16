"""
语义记忆提取

每轮对话结束后，用 LLM 从对话中提取关于用户项目的永久性事实。
"""

from memory.store import MemoryStore
from memory.types import MemoryItem

EXTRACT_PROMPT = """从以下对话中提取关于用户项目的永久性事实。

只提取确定的事实（技术栈、架构选择、约束条件、依赖等）。
不要提取临时性的、一次性的信息。
每条事实应该是一个简洁的陈述句。

输出 JSON 格式（只输出 JSON，不要其他文字）:
[
  {"fact": "项目使用 Rust + actix-web", "confidence": 0.95, "domain": "tech_stack"},
  {"fact": "用户关注性能优化", "confidence": 0.8, "domain": "preference"}
]

如果没有可提取的事实，输出: []

对话:
{conversation}
"""


def extract_semantic_memories(
    store: MemoryStore,
    llm_client,
    user_query: str,
    assistant_answer: str,
) -> list[str]:
    """
    从单轮对话中提取 semantic 记忆

    Args:
        store: MemoryStore 实例
        llm_client: LLMClient 实例
        user_query: 用户问题
        assistant_answer: AI 回答（通常是简要版或眼动偏好的那个）

    Returns:
        已添加的记忆 ID 列表
    """
    conversation = f"用户: {user_query}\n\n助手: {assistant_answer[:1000]}"

    try:
        response = llm_client.generate(
            system_prompt=EXTRACT_PROMPT,
            user_prompt=conversation,
            temperature=0.1,
            max_tokens=1000,
        )
        raw = response.text.strip()

        # 提取 JSON
        import re
        json_match = re.search(r"\[[\s\S]*\]", raw)
        if not json_match:
            return []

        facts = json_match.group()
        import json as json_lib
        parsed = json_lib.loads(facts)

        added_ids = []
        for fact in parsed:
            confidence = fact.get("confidence", 0.5)
            if confidence < 0.6:
                continue  # 置信度太低不存

            # 检查是否与已有事实冲突
            existing = _find_conflicting(store, fact["fact"])
            if existing:
                store.invalidate(existing.id)

            item_id = store.add_semantic(
                content=fact["fact"],
                source_query=user_query,
                confidence=confidence,
                metadata={"domain": fact.get("domain", "general")},
            )
            added_ids.append(item_id)

        return added_ids

    except Exception as e:
        print(f"  [Extractor] 提取 semantic 记忆失败: {e}")
        return []


def _find_conflicting(store: MemoryStore, new_fact: str) -> MemoryItem | None:
    """
    检查新事实是否与已有事实冲突

    简单规则：如果新事实包含 "改为"、"换成"、"不用" 等关键词，
    查找同领域的已有事实。
    """
    import re

    # 检测变更信号
    change_signals = ["改为", "换成", "换成", "迁移到", "改用", "不再使用"]
    has_change = any(s in new_fact for s in change_signals)

    if not has_change:
        return None

    # 尝试提取领域关键词
    # 简单做法：提取新事实中的关键名词
    for item in store.get_all("semantic"):
        # 如果新事实提到某个技术名，而旧事实也提到
        for token in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]+", new_fact):
            if token.lower() in item.content.lower():
                return item

    return None
