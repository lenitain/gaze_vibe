"""
结构化输出 Schema

定义 LLM 返回值的 Pydantic 模型，用于 function calling / JSON 模式约束。
所有模型有 from_json() / to_json() 方便序列化。
"""

import json
from typing import Any

from pydantic import BaseModel, Field

# ===== 核心输出 =====

class CodeBlock(BaseModel):
    """代码块"""
    language: str = Field(default="", description="编程语言")
    code: str = Field(default="", description="代码内容")
    file_path: str = Field(default="", description="建议的文件路径（如已知）")
    description: str = Field(default="", description="代码块的用途说明")


class SingleAnswer(BaseModel):
    """单个答案"""
    text: str = Field(default="", description="回答正文 (Markdown)")
    code_blocks: list[CodeBlock] = Field(default_factory=list, description="代码块列表")
    key_points: list[str] = Field(default_factory=list, description="关键要点")


class DualAnswer(BaseModel):
    """双答案输出 — 一次调用返回两个风格"""
    answer_a: SingleAnswer = Field(description="详细解答（注释丰富、讲解详细）")
    answer_b: SingleAnswer = Field(description="简洁解答（精简干练、无注释）")


class AnswerSegment(BaseModel):
    """子问题 — 对应问题分割中的一个片段"""
    id: str = Field(description="子问题 ID")
    prompt: str = Field(description="子问题内容")
    context_hint: str = Field(default="", description="上下文提示")
    depends_on: str = Field(default="", description="依赖的上一个子问题 ID")


class SubQuestions(BaseModel):
    """问题分割结果"""
    segments: list[AnswerSegment] = Field(description="子问题列表")


# ===== 工具函数 =====

def schema_to_function(name: str, description: str, model: type[BaseModel]) -> dict:
    """
    将 Pydantic 模型转换为 function calling schema

    Args:
        name: 函数名
        description: 函数描述
        model: Pydantic 模型类

    Returns:
        dict: OpenAI-compatible function calling schema
    """
    schema = model.model_json_schema()

    # 清理 Pydantic 特有的 metadata
    _clean_schema(schema)

    return {
        "name": name,
        "description": description,
        "parameters": schema,
    }


def _clean_schema(schema: dict):
    """递归清理 Pydantic schema 中的非标准字段"""
    for key in list(schema.keys()):
        if key.startswith("$") or key in ("title", "default"):
            if key != "$ref":
                schema.pop(key, None)

    if "properties" in schema:
        for prop in schema["properties"].values():
            if isinstance(prop, dict):
                _clean_schema(prop)

    if "items" in schema and isinstance(schema["items"], dict):
        _clean_schema(schema["items"])

    if "anyOf" in schema:
        for item in schema["anyOf"]:
            if isinstance(item, dict):
                _clean_schema(item)

    for ref_key in ("$defs", "definitions"):
        if ref_key in schema:
            for def_item in schema[ref_key].values():
                if isinstance(def_item, dict):
                    _clean_schema(def_item)


def extract_structured_response(text: str) -> dict[str, Any] | None:
    """
    从 LLM 响应文本中提取结构化数据。

    当 function calling 失败或 fallback 到纯文本时，
    尝试从 markdown 代码块中解析 JSON。
    """
    if not text:
        return None

    # 尝试直接解析
    text = text.strip()
    if text.startswith("{"):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

    # 尝试从 ```json 块中提取
    import re
    match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    return None


def parse_dual_answer(text: str) -> DualAnswer | None:
    """从文本解析 DualAnswer"""
    data = extract_structured_response(text)
    if data:
        try:
            return DualAnswer.model_validate(data)
        except Exception:
            pass
    return None
