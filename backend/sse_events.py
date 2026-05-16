"""
SSE 流式事件协议

定义所有 SSE 事件类型，统一序列化格式。
前后端共用此事件类型约定。

事件类型:
- text_start: 文本开始
- text_delta: 文本增量（逐字/逐块）
- text_end: 文本结束
- segment_start: 子问题开始
- segment_end: 子问题结束
- tool_call: LLM 请求调用工具
- tool_result: 工具返回结果
- eye_adjustment: 眼动调整状态更新
- done: 全部完成
- error: 发生错误
"""

import json
from typing import Any
from dataclasses import dataclass, field, asdict
from datetime import datetime


# ===== 事件数据类型 =====

@dataclass
class SSEEvent:
    """SSE 事件基类"""
    type: str

    def to_dict(self) -> dict:
        return {"type": self.type}

    def to_sse(self) -> str:
        """序列化为 SSE 格式 (data: {...}\n\n)"""
        return f"data: {json.dumps(self.to_dict(), ensure_ascii=False)}\n\n"


@dataclass
class TextStart(SSEEvent):
    """文本开始"""
    type: str = "text_start"
    segment_id: str = ""
    style: str = ""  # "detailed" | "concise"

    def to_dict(self) -> dict:
        return {"type": self.type, "segmentId": self.segment_id, "style": self.style}


@dataclass
class TextDelta(SSEEvent):
    """文本增量"""
    type: str = "text_delta"
    segment_id: str = ""
    style: str = ""
    text: str = ""

    def to_dict(self) -> dict:
        return {"type": self.type, "segmentId": self.segment_id, "style": self.style, "text": self.text}


@dataclass
class TextEnd(SSEEvent):
    """文本结束"""
    type: str = "text_end"
    segment_id: str = ""
    style: str = ""
    full_text: str = ""
    latency_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "segmentId": self.segment_id,
            "style": self.style,
            "fullText": self.full_text,
            "latencyMs": self.latency_ms,
        }


@dataclass
class SegmentStart(SSEEvent):
    """子问题开始"""
    type: str = "segment_start"
    index: int = 0
    total: int = 1
    id: str = ""
    context_hint: str = ""

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "index": self.index,
            "total": self.total,
            "id": self.id,
            "contextHint": self.context_hint,
        }


@dataclass
class SegmentEnd(SSEEvent):
    """子问题结束"""
    type: str = "segment_end"
    index: int = 0
    total: int = 1
    id: str = ""
    success: bool = True

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "index": self.index,
            "total": self.total,
            "id": self.id,
            "success": self.success,
        }


@dataclass
class ToolCall(SSEEvent):
    """LLM 请求调用工具"""
    type: str = "tool_call"
    tool_name: str = ""
    arguments: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"type": self.type, "toolName": self.tool_name, "arguments": self.arguments}


@dataclass
class ToolResult(SSEEvent):
    """工具返回结果"""
    type: str = "tool_result"
    tool_name: str = ""
    success: bool = True
    summary: str = ""

    def to_dict(self) -> dict:
        return {"type": self.type, "toolName": self.tool_name, "success": self.success, "summary": self.summary}


@dataclass
class EyeAdjustment(SSEEvent):
    """眼动调整状态更新"""
    type: str = "eye_adjustment"
    detail_score: float = 0.5
    explanation_score: float = 0.5
    persona_bias: float = 0.5
    confidence: float = 0.0
    round_count: int = 0
    preferred_side: str | None = None

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "detailScore": self.detail_score,
            "explanationScore": self.explanation_score,
            "personaBias": self.persona_bias,
            "confidence": self.confidence,
            "roundCount": self.round_count,
            "preferredSide": self.preferred_side,
        }


@dataclass
class Done(SSEEvent):
    """全部完成"""
    type: str = "done"
    experiment_mode: str = "full"
    adjustments: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"type": self.type, "experimentMode": self.experiment_mode, "adjustments": self.adjustments}


@dataclass
class Error(SSEEvent):
    """发生错误"""
    type: str = "error"
    message: str = ""
    code: str = "unknown"

    def to_dict(self) -> dict:
        return {"type": self.type, "message": self.message, "code": self.code}


# ===== 事件工厂 =====

def create_segment_start(index: int, total: int, segment_id: str, hint: str = "") -> str:
    return SegmentStart(index=index, total=total, id=segment_id, context_hint=hint).to_sse()


def create_segment_end(index: int, total: int, segment_id: str, success: bool = True) -> str:
    return SegmentEnd(index=index, total=total, id=segment_id, success=success).to_sse()


def create_text_delta(segment_id: str, style: str, text: str) -> str:
    return TextDelta(segment_id=segment_id, style=style, text=text).to_sse()


def create_text_end(segment_id: str, style: str, full_text: str, latency_ms: float = 0) -> str:
    return TextEnd(segment_id=segment_id, style=style, full_text=full_text, latency_ms=latency_ms).to_sse()


def create_eye_adjustment(
    detail: float, explanation: float, persona_bias: float,
    confidence: float, round_count: int
) -> str:
    preferred = "A" if detail > 0.5 else "B" if detail < 0.5 else None
    return EyeAdjustment(
        detail_score=detail,
        explanation_score=explanation,
        persona_bias=persona_bias,
        confidence=confidence,
        round_count=round_count,
        preferred_side=preferred,
    ).to_sse()


def create_done(experiment_mode: str, adjustments: dict) -> str:
    return Done(experiment_mode=experiment_mode, adjustments=adjustments).to_sse()


def create_error(message: str, code: str = "unknown") -> str:
    return Error(message=message, code=code).to_sse()
