"""
Agent Loop — 多轮 tool calling

流程：
  1. 调用 LLM（messages + tools）
  2. 如果响应含 tool_call → 执行 → 结果追加 → goto 1
  3. 如果无 tool_call → 返回最终文本 + tool 调用记录

支持最多 max_turns 轮，防无限循环。
"""

import json
from dataclasses import dataclass, field

from llm_client import LLMClient, LLMError


@dataclass
class ToolCallRecord:
    """单次 tool 调用记录"""
    turn: int
    tool: str
    args: dict
    result: str  # 截断到 500 字符


@dataclass
class AgentResult:
    """Agent 执行结果"""
    text: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    turn_count: int = 0
    success: bool = True


class AgentLoop:
    """
    多轮 tool calling 循环

    每次迭代：
    1. 调用 LLM（messages + tools）
    2. 如果有 tool_call → 执行 → 追加消息 → 回到 1
    3. 如果无 → 返回最终文本
    """

    def __init__(
        self,
        llm: LLMClient,
        tools: list,
        max_turns: int = 6,
        model: str = "deepseek-chat",
    ):
        """
        Args:
            llm: LLMClient 实例
            tools: Tool 对象列表（tool_agent.Tool）
            max_turns: 最大迭代轮数
            model: 使用的模型名
        """
        self.llm = llm
        self.tools = {t.name: t for t in tools}
        self.max_turns = max_turns
        self.model = model

    def run(
        self,
        system_prompt: str,
        user_prompt: str,
        context_messages: list[dict] | None = None,
    ) -> dict:
        """
        执行 agent

        Args:
            system_prompt: 系统 prompt
            user_prompt: 用户问题
            context_messages: 可选的上下文消息（如 RAG 检索结果）

        Returns:
            {"text": str, "tool_calls": list, "turn_count": int, "success": bool}
        """
        messages = [{"role": "system", "content": system_prompt}]
        if context_messages:
            messages.extend(context_messages)
        messages.append({"role": "user", "content": user_prompt})

        tool_calls_log: list[ToolCallRecord] = []
        final_text = ""

        for turn in range(self.max_turns):
            try:
                response = self.llm.generate(
                    system_prompt="",  # 放在 messages 里
                    user_prompt="",
                    messages=messages,
                    tools=self._get_tool_schemas(),
                    tool_choice="auto",
                    temperature=0.3,
                    max_tokens=4000,
                )
            except LLMError as e:
                return {
                    "text": f"Agent 执行失败: {e}",
                    "tool_calls": [t.__dict__ for t in tool_calls_log],
                    "turn_count": turn + 1,
                    "success": False,
                }

            choice = response.choices[0]
            msg = choice.message

            if msg.content:
                final_text = msg.content

            if not msg.tool_calls:
                return {
                    "text": final_text,
                    "tool_calls": [t.__dict__ for t in tool_calls_log],
                    "turn_count": turn + 1,
                    "success": True,
                }

            # 执行 tool calls
            for tc in msg.tool_calls:
                tool_name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                tool = self.tools.get(tool_name)
                if tool is None:
                    result = f"未知 tool: {tool_name}"
                else:
                    try:
                        result = tool.handler(**args)
                    except Exception as e:
                        result = f"执行失败: {e}"

                # 截断结果
                truncated = str(result)[:500]
                tool_calls_log.append(ToolCallRecord(
                    turn=turn,
                    tool=tool_name,
                    args=args,
                    result=truncated,
                ))

                # 追加到消息列表
                messages.append(msg)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": truncated,
                })

        # 超过 max_turns
        return {
            "text": final_text,
            "tool_calls": [t.__dict__ for t in tool_calls_log],
            "turn_count": self.max_turns,
            "success": True,
        }

    def _get_tool_schemas(self) -> list[dict]:
        """将 Tool 对象转为 OpenAI function calling schema"""
        schemas = []
        for tool in self.tools.values():
            schemas.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            })
        return schemas
