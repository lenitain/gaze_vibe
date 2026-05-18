"""
LLM 客户端层

替代裸 openai client.chat.completions.create() 调用，提供：
- retry + exponential backoff
- 流式 / 非流式统一接口
- Token 用量精确追踪
- 超时控制
- 模型 fallback
- 结构化输出 (function calling)
- 调用日志回调
"""

import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import openai
from openai import OpenAI

from config import (
    ANSWER_MAX_TOKENS,
    ANSWER_TEMPERATURE,
    LLM_BASE_URL,
    LLM_MAX_RETRIES,
    LLM_MODEL,
    LLM_TIMEOUT,
)

# ===== 数据类型 =====

@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    def add(self, other: "TokenUsage") -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.total_tokens += other.total_tokens


@dataclass
class LLMCallRecord:
    """单次 LLM 调用的完整记录"""
    timestamp: str = ""
    model: str = ""
    system_prompt_preview: str = ""
    user_prompt_preview: str = ""
    response_preview: str = ""
    latency_ms: float = 0.0
    usage: TokenUsage = field(default_factory=TokenUsage)
    success: bool = True
    error: str = ""
    retry_count: int = 0


@dataclass
@dataclass
class ToolCallInfo:
    """单次 tool_call 信息"""
    id: str
    name: str
    arguments: str  # JSON string


@dataclass
class LLMResponse:
    """LLM 调用响应

    text: 响应文本（无 tool_call 时 = content，有 tool_call 时 = 空）
    usage: token 用量
    model: 模型名
    latency_ms: 延迟
    tool_calls: 可选，function calling 请求列表
    """
    text: str
    usage: TokenUsage
    model: str
    latency_ms: float
    tool_calls: list[ToolCallInfo] | None = None

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


# ===== 配置 =====

DEFAULT_MODEL = LLM_MODEL
DEFAULT_BASE_URL = LLM_BASE_URL
DEFAULT_MAX_RETRIES = LLM_MAX_RETRIES
DEFAULT_TIMEOUT = LLM_TIMEOUT
DEFAULT_TEMPERATURE = ANSWER_TEMPERATURE
DEFAULT_MAX_TOKENS = ANSWER_MAX_TOKENS

# fallback 模型链 (按优先级)
FALLBACK_MODELS = [
    LLM_MODEL,
]


# ===== Token 追踪器 =====

class TokenTracker:
    """累积 token 用量统计"""

    def __init__(self):
        self.reset()

    def reset(self):
        self.session_usage = TokenUsage()
        self.call_records: list[LLMCallRecord] = []

    @property
    def total_input(self) -> int:
        return self.session_usage.input_tokens

    @property
    def total_output(self) -> int:
        return self.session_usage.output_tokens

    @property
    def total_tokens(self) -> int:
        return self.session_usage.total_tokens

    def record(self, record: LLMCallRecord):
        self.call_records.append(record)
        if record.success:
            self.session_usage.add(record.usage)

    def summary(self) -> dict:
        return {
            "total_calls": len(self.call_records),
            "successful": sum(1 for r in self.call_records if r.success),
            "failed": sum(1 for r in self.call_records if not r.success),
            "total_input_tokens": self.total_input,
            "total_output_tokens": self.total_output,
            "total_tokens": self.total_tokens,
        }


# ===== 回调类型 =====

OnTextFn = Callable[[str], None]
OnToolCallFn = Callable[[str, str, dict], None]
OnUsageFn = Callable[[TokenUsage], None]
OnRecordFn = Callable[[LLMCallRecord], None]


# ===== 主客户端 =====

class LLMClient:
    """
    统一 LLM 调用客户端

    Usage:
        client = LLMClient()
        resp = client.generate(
            system_prompt="...",
            user_prompt="...",
        )
        print(resp.text)

        # 流式:
        texts = []
        resp = client.generate_stream(
            system_prompt="...",
            user_prompt="...",
            on_text=lambda t: texts.append(t),
        )
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        max_retries: int = DEFAULT_MAX_RETRIES,
        timeout: int = DEFAULT_TIMEOUT,
        on_record: OnRecordFn | None = None,
    ):
        self.model = model
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = base_url
        self.max_retries = max_retries
        self.timeout = timeout
        self.on_record = on_record

        self._client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )
        self.stats = TokenTracker()
        self._provider_errors: list[str] = []

    # ----- 非流式生成 -----

    def generate(
        self,
        system_prompt: str = "",
        user_prompt: str = "",
        messages: list[dict] | None = None,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        model: str | None = None,
        retry: int | None = None,
        tools: list[dict] | None = None,
        tool_choice: str | dict | None = None,
    ) -> LLMResponse:
        """
        非流式生成，带 retry 和 fallback

        如果提供了 messages，直接使用（覆盖 system_prompt + user_prompt）。
        """
        return self._generate_with_retry(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            model=model or self.model,
            retry=retry if retry is not None else self.max_retries,
            stream=False,
            tools=tools,
            tool_choice=tool_choice,
        )

    # ----- 流式生成 -----

    def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        on_text: OnTextFn | None = None,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        model: str | None = None,
        retry: int | None = None,
    ) -> LLMResponse:
        """
        流式生成，on_text 在每个 delta 到达时被调用
        """
        return self._generate_with_retry(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            model=model or self.model,
            retry=retry if retry is not None else self.max_retries,
            stream=True,
            on_text=on_text,
        )

    # ----- 结构化输出 (function calling) -----

    def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: dict | type,
        temperature: float = DEFAULT_TEMPERATURE,
        model: str | None = None,
        retry: int | None = None,
    ) -> LLMResponse:
        """
        使用 function calling 生成结构化输出

        schema 可以是:
        1. dict: 原始 function calling schema
            {
                "name": "extract_answer",
                "description": "...",
                "parameters": { ... }
            }
        2. Pydantic BaseModel 类: 自动转换为 schema
        """
        # 如果传入的是 Pydantic 模型类，自动转换
        if isinstance(schema, type) and hasattr(schema, 'model_json_schema'):
            from schemas import schema_to_function
            schema = schema_to_function(
                name=schema.__name__,
                description=schema.__doc__ or f"Structured output for {schema.__name__}",
                model=schema,
            )

        # 参数校验
        if not isinstance(schema, dict) or "name" not in schema or "parameters" not in schema:
            raise ValueError(
                'schema 必须是 dict 格式 {name, description, parameters} '
                '或 Pydantic BaseModel 子类'
            )

        return self._generate_with_retry(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=DEFAULT_MAX_TOKENS,
            model=model or self.model,
            retry=retry if retry is not None else self.max_retries,
            stream=False,
            tools=[{
                "type": "function",
                "function": schema,
            }],
            tool_choice={"type": "function", "function": {"name": schema["name"]}},
        )

    # ----- 核心调用逻辑 -----

    def _generate_with_retry(
        self,
        system_prompt: str,
        user_prompt: str,
        messages: list[dict] | None = None,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        model: str | None = None,
        retry: int = 0,
        stream: bool = False,
        on_text: OnTextFn | None = None,
        tools: list[dict] | None = None,
        tool_choice: dict | None = None,
    ) -> LLMResponse:
        """带 retry + fallback 的核心调用"""
        if model is None:
            model = self.model
        last_error = ""
        models_to_try = [model] + [m for m in FALLBACK_MODELS if m != model]

        for attempt in range(max(1, retry + 1)):
            # 决定用哪个模型
            current_model = models_to_try[0]
            if attempt > 0 and len(models_to_try) > 1:
                # 重试时尝试 fallback 模型
                fallback_idx = min(attempt, len(models_to_try) - 1)
                current_model = models_to_try[fallback_idx]
                print(f"  [LLM] fallback 到模型: {current_model} (attempt {attempt})")

            try:
                return self._call(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    model=current_model,
                    stream=stream,
                    on_text=on_text,
                    tools=tools,
                    tool_choice=tool_choice,
                )
            except openai.RateLimitError as e:
                wait = min(2 ** attempt * 2, 30)  # 指数退避
                print(f"  [LLM] 速率限制，等待 {wait}s (attempt {attempt + 1}): {e}")
                time.sleep(wait)
                last_error = str(e)
            except openai.APITimeoutError as e:
                print(f"  [LLM] 超时 (attempt {attempt + 1}): {e}")
                last_error = str(e)
            except openai.APIError as e:
                print(f"  [LLM] API 错误 (attempt {attempt + 1}): {e}")
                last_error = str(e)
            except Exception as e:
                print(f"  [LLM] 未知错误 (attempt {attempt + 1}): {e}")
                last_error = str(e)
                break  # 未知错误不重试

        # 所有重试失败
        record = LLMCallRecord(
            timestamp=datetime.now().isoformat(),
            model=model,
            system_prompt_preview=system_prompt[:100],
            user_prompt_preview=user_prompt[:100],
            response_preview="",
            latency_ms=0,
            success=False,
            error=last_error,
            retry_count=retry,
        )
        self._emit_record(record)
        raise LLMError(f"LLM 调用失败 (重试 {retry} 次): {last_error}")

    def _call(
        self,
        system_prompt: str,
        user_prompt: str,
        messages: list[dict] | None = None,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        model: str | None = None,
        stream: bool = False,
        on_text: OnTextFn | None = None,
        tools: list[dict] | None = None,
        tool_choice: dict | None = None,
    ) -> LLMResponse:
        """单次 LLM API 调用"""
        if model is None:
            model = self.model
        start_time = time.time()
        if messages is not None:
            msgs = messages
        else:
            msgs = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

        kwargs: dict[str, Any] = dict(
            model=model,
            messages=msgs,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=self.timeout,
        )
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice

        if stream:
            kwargs["stream"] = True
            return self._call_stream(kwargs, model, start_time, on_text, system_prompt, user_prompt)

        response = self._client.chat.completions.create(**kwargs)
        elapsed = (time.time() - start_time) * 1000

        choice = response.choices[0]
        msg = choice.message
        text = msg.content or ""

        # 提取 tool_calls (用于 Agent Loop)
        tool_calls: list[ToolCallInfo] | None = None
        if msg.tool_calls:
            tool_calls = []
            for tc in msg.tool_calls:
                tool_calls.append(ToolCallInfo(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=tc.function.arguments,
                ))

        usage = TokenUsage(
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
            total_tokens=response.usage.total_tokens if response.usage else 0,
        )

        record = LLMCallRecord(
            timestamp=datetime.now().isoformat(),
            model=model,
            system_prompt_preview=system_prompt[:100],
            user_prompt_preview=user_prompt[:100],
            response_preview=text[:200] or str(tool_calls[:1]) if tool_calls else "",
            latency_ms=round(elapsed, 1),
            usage=usage,
            success=True,
        )
        self._emit_record(record)

        return LLMResponse(
            text=text,
            usage=usage,
            model=model,
            latency_ms=round(elapsed, 1),
            tool_calls=tool_calls,
        )

    def _call_stream(
        self,
        kwargs: dict,
        model: str,
        start_time: float,
        on_text: OnTextFn | None,
        system_prompt: str,
        user_prompt: str,
    ) -> LLMResponse:
        """流式调用"""
        collected_text = ""
        response = self._client.chat.completions.create(**kwargs)

        for chunk in response:
            if chunk.choices and chunk.choices[0].delta:
                delta = chunk.choices[0].delta
                if delta.content:
                    collected_text += delta.content
                    if on_text:
                        on_text(delta.content)

        elapsed = (time.time() - start_time) * 1000

        # 最后的 chunk 带有 usage
        usage = TokenUsage()
        if hasattr(response, "_usage") and response._usage:
            usage = TokenUsage(
                input_tokens=response._usage.prompt_tokens or 0,
                output_tokens=response._usage.completion_tokens or 0,
                total_tokens=response._usage.total_tokens or 0,
            )

        record = LLMCallRecord(
            timestamp=datetime.now().isoformat(),
            model=model,
            system_prompt_preview=system_prompt[:100],
            user_prompt_preview=user_prompt[:100],
            response_preview=collected_text[:200],
            latency_ms=round(elapsed, 1),
            usage=usage,
            success=True,
        )
        self._emit_record(record)

        return LLMResponse(text=collected_text, usage=usage, model=model, latency_ms=round(elapsed, 1))

    def _emit_record(self, record: LLMCallRecord):
        """发出调用记录"""
        self.stats.record(record)
        if self.on_record:
            try:
                self.on_record(record)
            except Exception:
                pass


# ===== 异常 =====

class LLMError(Exception):
    """LLM 调用异常"""
    pass
