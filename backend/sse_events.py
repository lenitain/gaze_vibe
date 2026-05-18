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
from dataclasses import dataclass, field

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


# ===== Agent 生命周期事件（Phase 2, 参考 pi AgentEvent） =====

@dataclass
class SessionStart(SSEEvent):
    """Session 开始"""
    type: str = "session_start"
    session_id: str = ""
    project_name: str = "default"
    timestamp: str = ""

    def to_dict(self) -> dict:
        return {"type": self.type, "sessionId": self.session_id,
                "projectName": self.project_name, "timestamp": self.timestamp}


@dataclass
class TurnStart(SSEEvent):
    """Turn 开始（一次用户交互）"""
    type: str = "turn_start"
    turn_id: str = ""
    session_id: str = ""
    question: str = ""

    def to_dict(self) -> dict:
        return {"type": self.type, "turnId": self.turn_id,
                "sessionId": self.session_id, "question": self.question}


@dataclass
class MessageStart(SSEEvent):
    """消息开始（一个答案开始生成）"""
    type: str = "message_start"
    turn_id: str = ""
    style: str = ""  # "detailed" | "concise"

    def to_dict(self) -> dict:
        return {"type": self.type, "turnId": self.turn_id, "style": self.style}


@dataclass
class MessageDelta(SSEEvent):
    """消息增量"""
    type: str = "message_delta"
    turn_id: str = ""
    style: str = ""
    text: str = ""

    def to_dict(self) -> dict:
        return {"type": self.type, "turnId": self.turn_id,
                "style": self.style, "text": self.text}


@dataclass
class MessageEnd(SSEEvent):
    """消息结束"""
    type: str = "message_end"
    turn_id: str = ""
    style: str = ""
    full_text: str = ""

    def to_dict(self) -> dict:
        return {"type": self.type, "turnId": self.turn_id,
                "style": self.style, "fullText": self.full_text}


@dataclass
class ToolCallExec(SSEEvent):
    """工具执行（后端静默执行时可选推送进度）"""
    type: str = "tool_call_exec"
    turn_id: str = ""
    tool_name: str = ""
    status: str = "running"  # "running" | "done" | "error"

    def to_dict(self) -> dict:
        return {"type": self.type, "turnId": self.turn_id,
                "toolName": self.tool_name, "status": self.status}


@dataclass
class SessionEnd(SSEEvent):
    """Session 结束"""
    type: str = "session_end"
    session_id: str = ""
    total_turns: int = 0

    def to_dict(self) -> dict:
        return {"type": self.type, "sessionId": self.session_id,
                "totalTurns": self.total_turns}


# AgentEvent 联合类型（参考 pi 的 AgentEvent）
type AgentEvent = (
    SessionStart | TurnStart | MessageStart | MessageDelta | MessageEnd
    | ToolCallExec | EyeAdjustment | SessionEnd
    | SegmentStart | SegmentEnd | TextStart | TextDelta | TextEnd
    | ToolCall | ToolResult | Done | Error
)


# ===== 新事件工厂 =====

def create_session_start(session_id: str, project_name: str = "default", timestamp: str | None = None) -> str:
    from datetime import datetime
    return SessionStart(
        session_id=session_id,
        project_name=project_name,
        timestamp=timestamp or datetime.now().isoformat(),
    ).to_sse()


def create_turn_start(turn_id: str, session_id: str, question: str) -> str:
    return TurnStart(turn_id=turn_id, session_id=session_id, question=question[:200]).to_sse()


def create_message_start(turn_id: str, style: str) -> str:
    return MessageStart(turn_id=turn_id, style=style).to_sse()


def create_message_delta(turn_id: str, style: str, text: str) -> str:
    return MessageDelta(turn_id=turn_id, style=style, text=text).to_sse()


def create_message_end(turn_id: str, style: str, full_text: str) -> str:
    return MessageEnd(turn_id=turn_id, style=style, full_text=full_text).to_sse()


def create_tool_call_exec(turn_id: str, tool_name: str, status: str = "running") -> str:
    return ToolCallExec(turn_id=turn_id, tool_name=tool_name, status=status).to_sse()


def create_session_end(session_id: str, total_turns: int = 0) -> str:
    return SessionEnd(session_id=session_id, total_turns=total_turns).to_sse()


# ===== 事件工厂（原有，保持向后兼容） =====

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
