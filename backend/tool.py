"""
统一 Tool 定义

GazeVibe 工具系统：
- Tool: 工具定义（name/description/parameters/handler）
- 工具工厂: 创建具体工具实例
- 路径安全: 防止路径穿越攻击
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ===== Tool 定义 =====

ToolHandler = Callable[..., str]

TOOL_OUTPUT_MAX_CHARS = 3000
"""工具输出最大字符数，超出截断"""


@dataclass
class Tool:
    """统一工具定义"""
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema
    handler: ToolHandler

    def to_openai_schema(self) -> dict:
        """转为 OpenAI function calling schema"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def execute(self, **kwargs) -> str:
        """执行工具，返回结果文本"""
        result = self.handler(**kwargs)
        if len(result) > TOOL_OUTPUT_MAX_CHARS:
            result = result[:TOOL_OUTPUT_MAX_CHARS] + f"\n... (截断, 共 {len(result)} 字符)"
        return result


# ===== 路径安全 =====

IGNORE_DIRS = {"node_modules", ".git", "dist", "build", "__pycache__", ".venv", "venv", ".idea", ".vscode", ".ruff_cache", ".pytest_cache"}


def resolve_project_path(project_root: str, file_path: str) -> Path:
    """将相对路径解析为项目绝对路径，防止路径穿越"""
    root = Path(project_root).resolve()
    target = (root / file_path).resolve()
    if not str(target).startswith(str(root)):
        raise ValueError(f"路径越界: {file_path}")
    return target


# ===== 工具工厂 =====

def make_read_file_tool(project_root: str) -> Tool:
    """读取文件"""
    def handler(file_path: str) -> str:
        target = resolve_project_path(project_root, file_path)
        if not target.exists():
            return f"文件不存在: {file_path}"
        if not target.is_file():
            return f"不是文件: {file_path}"
        try:
            content = target.read_text(encoding="utf-8")
            return f"文件 {file_path} ({len(content)} 字符):\n```\n{content}\n```"
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
    """写入/覆盖文件"""
    def handler(file_path: str, content: str) -> str:
        target = resolve_project_path(project_root, file_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        exists = target.exists()
        target.write_text(content, encoding="utf-8")
        action = "创建" if not exists else "更新"
        return f"✓ 已{action}文件: {file_path} ({len(content)} 字符)"

    return Tool(
        name="write_file",
        description="创建或覆盖项目文件。内容会完整写入，多次调用可逐步构建项目。",
        parameters={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "相对于项目根目录的文件路径，如 src/main.py",
                },
                "content": {
                    "type": "string",
                    "description": "文件完整内容",
                },
            },
            "required": ["file_path", "content"],
        },
        handler=handler,
    )


def make_search_code_tool(project_root: str) -> Tool:
    """搜索代码（grep）"""
    def handler(pattern: str, file_pattern: str = "*") -> str:
        results: list[str] = []
        root = Path(project_root).resolve()
        for fpath in root.rglob(file_pattern):
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
                    "description": "文件通配模式，如 *.py, *.rs, **/*.ts",
                },
            },
            "required": ["pattern"],
        },
        handler=handler,
    )


def make_list_files_tool(project_root: str) -> Tool:
    """列出目录结构"""
    def handler(dir_path: str = ".", depth: int = 2) -> str:
        root = Path(project_root).resolve()
        target = resolve_project_path(project_root, dir_path)
        if not target.exists():
            return f"目录不存在: {dir_path}"
        if not target.is_dir():
            return f"不是目录: {dir_path}"
        results: list[str] = []
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


def make_create_directory_tool(project_root: str) -> Tool:
    """创建目录"""
    def handler(dir_path: str) -> str:
        target = resolve_project_path(project_root, dir_path)
        if target.exists():
            return f"目录已存在: {dir_path}"
        target.mkdir(parents=True, exist_ok=True)
        return f"✓ 已创建目录: {dir_path}"

    return Tool(
        name="create_directory",
        description="在项目中创建新目录。当需要新建模块、组件目录时调用。",
        parameters={
            "type": "object",
            "properties": {
                "dir_path": {
                    "type": "string",
                    "description": "相对于项目根目录的目录路径，如 src/utils",
                }
            },
            "required": ["dir_path"],
        },
        handler=handler,
    )


# ===== 默认工具集 =====

def default_tools(project_root: str) -> list[Tool]:
    """获取默认工具集"""
    return [
        make_read_file_tool(project_root),
        make_write_file_tool(project_root),
        make_search_code_tool(project_root),
        make_list_files_tool(project_root),
        make_create_directory_tool(project_root),
    ]
