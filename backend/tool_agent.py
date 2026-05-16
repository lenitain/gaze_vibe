"""
代码应用 Agent

LLM 通过 tools 直接操作文件系统，替代当前前端解析代码块 → 手动点击的模式。

Tools:
- read_file: 读取项目文件
- write_file: 写入/修改文件
- search_code: 搜索项目代码
- list_files: 列出目录文件

Agent Loop:
1. 接收用户 prompt
2. LLM 决定调用哪些 tool（自然多步）
3. 执行 tool 返回结果
4. LLM 分析结果，决定下一步（继续调用 tool 或输出最终答案）
"""

import os
import json
import fnmatch
from pathlib import Path
from typing import Any, Callable
from dataclasses import dataclass, field

from llm_client import LLMClient, LLMResponse, LLMError


# ===== Tool 定义 =====

ToolHandler = Callable[..., str]


@dataclass
class Tool:
    """工具定义"""
    name: str
    description: str
    parameters: dict  # JSON Schema
    handler: ToolHandler


def _resolve_project_path(project_root: str, file_path: str) -> Path:
    """将相对路径解析为项目绝对路径，防止路径穿越"""
    root = Path(project_root).resolve()
    target = (root / file_path).resolve()
    if not str(target).startswith(str(root)):
        raise ValueError(f"路径越界: {file_path}")
    return target


def make_read_file_tool(project_root: str) -> Tool:
    """创建 read_file tool"""
    def handler(file_path: str) -> str:
        target = _resolve_project_path(project_root, file_path)
        if not target.exists():
            return f"文件不存在: {file_path}"
        if not target.is_file():
            return f"不是文件: {file_path}"
        try:
            content = target.read_text(encoding="utf-8")
            return f"文件 {file_path} ({len(content)} 字符):\n```\n{content[:5000]}\n```"
        except Exception as e:
            return f"读取失败: {e}"

    return Tool(
        name="read_file",
        description="读取项目文件的内容。当需要了解项目已有代码时调用。",
        parameters={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "相对于项目根目录的文件路径，如 src/main.py",
                }
            },
            "required": ["file_path"],
        },
        handler=handler,
    )


def make_write_file_tool(project_root: str) -> Tool:
    """创建 write_file tool"""
    def handler(file_path: str, content: str, mode: str = "overwrite") -> str:
        target = _resolve_project_path(project_root, file_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        # 检查是否已存在
        exists = target.exists()

        if mode == "create" and exists:
            return f"文件已存在: {file_path} (使用 mode=overwrite 覆盖)"

        target.write_text(content, encoding="utf-8")
        action = "创建" if not exists else "更新"
        return f"✓ 已{action}文件: {file_path} ({len(content)} 字符)"

    return Tool(
        name="write_file",
        description="创建或覆盖项目中的文件。当需要生成或修改代码文件时调用。",
        parameters={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "相对于项目根目录的文件路径",
                },
                "content": {
                    "type": "string",
                    "description": "文件内容",
                },
                "mode": {
                    "type": "string",
                    "enum": ["overwrite", "create"],
                    "description": "overwrite=覆盖已有文件, create=仅新建",
                },
            },
            "required": ["file_path", "content"],
        },
        handler=handler,
    )


def make_search_code_tool(project_root: str) -> Tool:
    """创建 search_code tool (简单 grep)"""
    # 排除目录
    IGNORE_DIRS = {"node_modules", ".git", "dist", "build", "__pycache__", ".venv", "venv", ".idea", ".vscode"}

    def handler(pattern: str, file_pattern: str = "*") -> str:
        results = []
        root = Path(project_root).resolve()

        for fpath in root.rglob(file_pattern):
            # 跳过排除目录
            rel = fpath.relative_to(root)
            if any(part in IGNORE_DIRS for part in rel.parts):
                continue
            if not fpath.is_file():
                continue

            try:
                content = fpath.read_text(encoding="utf-8", errors="ignore")
                for i, line in enumerate(content.split("\n"), 1):
                    if pattern.lower() in line.lower():
                        results.append(f"{rel}:{i}: {line.strip()[:200]}")
            except Exception:
                continue

            if len(results) >= 50:
                results.append("... (结果过多，已截断)")
                break

        if not results:
            return f"未找到匹配 '{pattern}' 的代码"
        return "\n".join(results[:50])

    return Tool(
        name="search_code",
        description="在项目文件中搜索代码。当需要定位特定函数、类或模式时调用。",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "搜索关键字（大小写不敏感）",
                },
                "file_pattern": {
                    "type": "string",
                    "description": "文件通配模式，如 *.py, *.js, **/*.ts",
                },
            },
            "required": ["pattern"],
        },
        handler=handler,
    )


def make_list_files_tool(project_root: str) -> Tool:
    """创建 list_files tool"""
    IGNORE_DIRS = {"node_modules", ".git", "dist", "build", "__pycache__", ".venv", "venv", ".idea", ".vscode"}

    def handler(dir_path: str = ".", depth: int = 2) -> str:
        root = Path(project_root).resolve()
        target = _resolve_project_path(project_root, dir_path)

        if not target.exists():
            return f"目录不存在: {dir_path}"
        if not target.is_dir():
            return f"不是目录: {dir_path}"

        results = []
        for fpath in target.rglob("*"):
            rel = fpath.relative_to(root)
            if any(part in IGNORE_DIRS for part in rel.parts):
                continue
            if len(rel.parts) > depth + 1:
                continue

            marker = "📁" if fpath.is_dir() else "📄"
            results.append(f"{marker} {rel}")

        if not results:
            return f"目录为空: {dir_path}"
        return "\n".join(sorted(results))

    return Tool(
        name="list_files",
        description="列出项目目录中的文件和子目录。当需要了解项目结构时调用。",
        parameters={
            "type": "object",
            "properties": {
                "dir_path": {
                    "type": "string",
                    "description": "相对于项目根目录的路径，默认为根目录",
                },
                "depth": {
                    "type": "integer",
                    "description": "递归深度，默认为 2",
                },
            },
        },
        handler=handler,
    )


# ===== Agent =====

@dataclass
class ToolCallRecord:
    """单次 tool 调用记录"""
    tool_name: str
    arguments: dict
    result: str
    success: bool


class ToolAgent:
    """
    代码应用 Agent

    管理 tool 执行循环：
    LLM 输出 tool_call → 执行 → 结果返回 → LLM 继续

    流程:
    for each turn:
        LLM 生成 (可能包含 tool_call)
        if tool_call:
            执行 tool → 结果 append 到消息列表
            continue
        else:
            输出最终答案
            break
    """

    def __init__(
        self,
        llm_client: LLMClient,
        project_root: str,
    ):
        self.llm = llm_client
        self.project_root = project_root
        self.tools: list[Tool] = [
            make_read_file_tool(project_root),
            make_write_file_tool(project_root),
            make_search_code_tool(project_root),
            make_list_files_tool(project_root),
        ]
        self.history: list[ToolCallRecord] = []

    def execute(
        self,
        system_prompt: str,
        user_prompt: str,
        max_turns: int = 5,
    ) -> AgentResult:
        """
        执行 agent，返回最终结果

        Args:
            system_prompt: 系统提示
            user_prompt: 用户提示
            max_turns: 最大 tool 调用轮次

        Returns:
            AgentResult: 包含最终文本、tool 调用记录等
        """
        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        self.history = []
        tool_schemas = self._get_tool_schemas()

        for turn in range(max_turns):
            try:
                response = self.llm.generate(
                    system_prompt="",
                    user_prompt="",
                    # 通过 messages 传完整的对话历史
                )
            except LLMError as e:
                return AgentResult(
                    success=False,
                    error=str(e),
                    tool_calls=self.history,
                )

        # 简化版：单次调用
        # 完整的 multi-turn agent 需要 function calling 支持多步 tool 调用
        return AgentResult(
            success=True,
            text="Tool agent 初始化完成（完整 multi-turn 需 function calling 支持）",
            tool_calls=[],
        )

    def _get_tool_schemas(self) -> list[dict]:
        """生成 OpenAI-compatible tool schemas"""
        schemas = []
        for tool in self.tools:
            schemas.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            })
        return schemas


@dataclass
class AgentResult:
    """Agent 执行结果"""
    success: bool = True
    text: str = ""
    error: str = ""
    tool_calls: list[ToolCallRecord] = field(default_factory=list)


# ===== 便捷工厂 =====

def create_tool_agent(
    project_root: str = ".",
    model: str = "deepseek-chat",
) -> ToolAgent:
    """创建预配置的 ToolAgent"""
    from llm_client import LLMClient
    client = LLMClient(model=model)
    return ToolAgent(llm_client=client, project_root=project_root)
