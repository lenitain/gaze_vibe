"""
文件写入器 — 从 LLM 回答中提取代码块并写入磁盘

不依赖 LLM 是否调用 function calling/tools，
直接从 markdown 代码块中提取文件路径标注并写入。

支持标注格式:
  // file: path/to/file.ext
  # file: path/to/file.ext
  <!-- file: path/to/file.ext -->
"""

from __future__ import annotations

import os
import re
from pathlib import Path


def extract_file_blocks(text: str) -> list[tuple[str, str]]:
    """
    从文本中提取带文件路径的代码块

    Returns:
        [(file_path, content), ...]
    """
    blocks: list[tuple[str, str]] = []

    # 匹配 ```lang\n// file: <path>\n<content>\n```
    # 或者 ```lang\n# file: <path>\n<content>\n```
    # file: 标注在第一行（紧跟 ```lang 之后）
    pattern_block = r'```\w*\n(?:(?://|#)\s*file:\s*(\S+))\s*\n([\s\S]*?)```'
    for m in re.finditer(pattern_block, text):
        file_path = m.group(1).strip()
        content = m.group(2).strip()
        if file_path and content:
            blocks.append((file_path, content))

    # 也匹配行内的 # file: 或 // file: （不强制在代码块开头）
    if not blocks:
        pattern_inline = r'(?:(?://|#)\s*file:\s*(\S+))\s*\n([\s\S]*?)(?=\n```|\Z)'
        for m in re.finditer(pattern_inline, text):
            file_path = m.group(1).strip()
            content = m.group(2).strip()
            if file_path and content:
                blocks.append((file_path, content))

    return blocks


def write_file_blocks(text: str, project_root: str) -> list[str]:
    """
    从文本中提取代码块并写入项目目录

    Args:
        text: LLM 回答文本（含 markdown 代码块 + file: 标注）
        project_root: 项目根目录

    Returns:
        已写入文件的路径列表（相对路径）
    """
    blocks = extract_file_blocks(text)
    if not blocks:
        return []

    root = Path(project_root).resolve()
    written: list[str] = []

    for file_path, content in blocks:
        # 防止路径穿越
        target = (root / file_path).resolve()
        if not str(target).startswith(str(root)):
            print(f"  [写文件] ⚠ 路径越界，跳过: {file_path}")
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        exists = target.exists()
        target.write_text(content, encoding="utf-8")
        action = "更新" if exists else "创建"
        written.append(file_path)
        print(f"  [写文件] ✓ {action}: {file_path} ({len(content)} 字符)")

    return written


def maybe_delete_file(project_root: str, file_path: str) -> bool:
    """
    安全删除项目中的文件（用于替换操作）

    检查路径安全后删除。
    """
    root = Path(project_root).resolve()
    target = (root / file_path).resolve()
    if not str(target).startswith(str(root)):
        print(f"  [删文件] ⚠ 路径越界，跳过: {file_path}")
        return False
    if not target.exists():
        return False
    if target.is_file():
        target.unlink()
        print(f"  [删文件] ✓ 删除: {file_path}")
        return True
    return False
