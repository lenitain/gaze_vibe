"""
Agent Loop — 多轮 tool calling

流程：
  1. 调用 LLM（messages + tools）
  2. 如果响应含 tool_calls → 执行 → 结果追加 → goto 1
  3. 如果无 tool_calls → 返回最终文本

关键原则（hideToolCalls）：
  - 调用方只看到最终文本，不知道中间 tool 执行
  - SSE 协议不变，前端零改动
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from config import AGENT_MAX_TOKENS, AGENT_MAX_TURNS, AGENT_TEMPERATURE
from llm_client import LLMClient, LLMError
from tool import Tool


@dataclass
class ToolCallRecord:
    """单次 tool 调用记录（供调用方日志使用）"""
    turn: int
    tool: str
    args: dict
    result: str  # 截断到 500 字符


@dataclass
class AgentResult:
    """Agent 执行结果"""
    text: str
    tool_calls: list[dict] = field(default_factory=list)
    turn_count: int = 0
    success: bool = True


class AgentLoop:
    """
    多轮 tool calling 循环

    Usage:
        agent = AgentLoop(llm_client, tools, max_turns=6)
        result = agent.run(system_prompt=prompt_a, user_prompt=prompt)
        answer = result.text  # 最终文本，中间 tool_call 对调用方不可见
    """

    def __init__(
        self,
        llm: LLMClient,
        tools: list[Tool],
        max_turns: int = AGENT_MAX_TURNS,
        max_tokens: int = AGENT_MAX_TOKENS,
    ):
        self.llm = llm
        self.tools = {t.name: t for t in tools}
        self.max_turns = max_turns
        self.max_tokens = max_tokens

    def run(
        self,
        system_prompt: str,
        user_prompt: str,
        context_messages: list[dict] | None = None,
    ) -> AgentResult:
        """
        执行 agent 循环

        Args:
            system_prompt: 系统提示
            user_prompt: 用户提示
            context_messages: 可选，附加对话历史

        Returns:
            AgentResult: 最终文本 + tool 调用日志
        """
        messages: list[dict] = [{"role": "system", "content": system_prompt}]
        if context_messages:
            messages.extend(context_messages)
        messages.append({"role": "user", "content": user_prompt})

        tool_calls_log: list[ToolCallRecord] = []
        final_text = ""
        tool_schemas = self._get_tool_schemas()

        for turn in range(self.max_turns):
            try:
                response = self.llm.generate(
                    messages=messages,
                    tools=tool_schemas,
                    tool_choice="auto",
                    temperature=AGENT_TEMPERATURE,
                    max_tokens=self.max_tokens,
                )
            except LLMError as e:
                print(f"  [Agent] 第 {turn + 1} 轮 LLM 调用失败: {e}")
                return AgentResult(
                    text=final_text or f"Agent 执行失败: {e}",
                    tool_calls=[t.__dict__ for t in tool_calls_log],
                    turn_count=turn + 1,
                    success=False,
                )

            # 累积文本
            if response.text:
                final_text = response.text

            # 检查是否有 tool_calls
            if not response.has_tool_calls:
                # 无 tool_call → 最终答案
                return AgentResult(
                    text=final_text,
                    tool_calls=[t.__dict__ for t in tool_calls_log],
                    turn_count=turn + 1,
                    success=True,
                )

            # 执行 tool calls（一轮可能多个并行）
            print(f"  [Agent] 第 {turn + 1} 轮: {len(response.tool_calls)} 个 tool_call")
            for tc_info in response.tool_calls:
                tool_name = tc_info.name
                try:
                    args = json.loads(tc_info.arguments)
                except json.JSONDecodeError:
                    print(f"  [Agent] tool {tool_name} 参数 JSON 解析失败: {tc_info.arguments[:100]}")
                    args = {}

                tool = self.tools.get(tool_name)
                if tool is None:
                    result = f"错误: 未知工具 '{tool_name}'"
                    print(f"  [Agent] ⚠ 未知 tool: {tool_name}")
                else:
                    try:
                        result = tool.execute(**args)
                        print(f"  [Agent] ✓ {tool_name}({json.dumps(args, ensure_ascii=False)[:100]})")
                    except Exception as e:
                        result = f"执行失败: {e}"
                        print(f"  [Agent] ✗ {tool_name} 执行错误: {e}")

                # 截断结果
                truncated = str(result)[:500]

                tool_calls_log.append(ToolCallRecord(
                    turn=turn,
                    tool=tool_name,
                    args=args,
                    result=truncated,
                ))

                # 追加 assistant 消息（含 tool_call）和 tool 结果到对话
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": tc_info.id,
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": tc_info.arguments,
                        },
                    }],
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_info.id,
                    "content": truncated,
                })

        # 超过 max_turns
        print(f"  [Agent] ⚠ 达到最大轮次 {self.max_turns}，返回当前文本")
        return AgentResult(
            text=final_text,
            tool_calls=[t.__dict__ for t in tool_calls_log],
            turn_count=self.max_turns,
            success=True,
        )

    def _get_tool_schemas(self) -> list[dict]:
        """将 Tool 列表转为 OpenAI function calling schema"""
        return [t.to_openai_schema() for t in self.tools.values()]
