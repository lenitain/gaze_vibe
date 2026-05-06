"""
Prompt 管理模块

遵循 pi-mono 的 prompt 工程理念：
- 所有 prompts 存放在独立 markdown 文件
- 每个文件有 frontmatter 元数据
- 通过此模块统一加载和访问
"""

import os
import re
from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent

# 缓存已加载的 prompts
_prompt_cache: dict[str, dict] = {}

# 模板占位符格式: {key_name}
_TEMPLATE_PATTERN = re.compile(r"\{(\w+)\}")


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """
    解析 markdown frontmatter (--- 包围的 YAML-like metadata)
    返回 (metadata_dict, body_text)
    """
    text = text.strip()
    if not text.startswith("---"):
        return {}, text

    # 找到第二个 ---
    end = text.find("---", 3)
    if end == -1:
        return {}, text

    meta_text = text[3:end].strip()
    body = text[end + 3 :].strip()

    metadata = {}
    for line in meta_text.split("\n"):
        line = line.strip()
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            metadata[key] = value

    return metadata, body


def load_prompt(name: str, variables: dict | None = None) -> str:
    """
    加载 prompt 文件内容

    Args:
        name: prompt 文件名（不含 .md 后缀）
        variables: 模板变量替换字典（可选）

    Returns:
        str: prompt 文本（不含 frontmatter）

    Raises:
        FileNotFoundError: 文件不存在
    """
    filepath = _PROMPTS_DIR / f"{name}.md"
    if not filepath.exists():
        # 如果没有 .md，尝试无后缀
        filepath = _PROMPTS_DIR / name
        if not filepath.exists():
            raise FileNotFoundError(f"Prompt 文件不存在: {name} (查找路径: {_PROMPTS_DIR})")

    raw = filepath.read_text(encoding="utf-8")
    _, body = _parse_frontmatter(raw)

    # 模板变量替换
    if variables:
        body = _TEMPLATE_PATTERN.sub(
            lambda m: str(variables.get(m.group(1), m.group(0))), body
        )

    return body


def get_prompt_metadata(name: str) -> dict:
    """
    获取 prompt 文件的 frontmatter 元数据

    Args:
        name: prompt 文件名（不含 .md 后缀）
    """
    filepath = _PROMPTS_DIR / f"{name}.md"
    if not filepath.exists():
        return {}

    raw = filepath.read_text(encoding="utf-8")
    metadata, _ = _parse_frontmatter(raw)
    return metadata


def list_prompts() -> list[dict]:
    """列出所有可用 prompt 及其元数据"""
    prompts = []
    for fpath in sorted(_PROMPTS_DIR.glob("*.md")):
        if fpath.name == "README.md":
            continue
        metadata = get_prompt_metadata(fpath.stem)
        prompts.append({"name": fpath.stem, "file": fpath.name, **metadata})
    return prompts


def reload_all():
    """清空缓存，下次加载时重新读取文件"""
    _prompt_cache.clear()
