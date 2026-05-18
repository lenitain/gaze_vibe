"""
问题拆分测试

测试 split_user_question 的拆分质量。
需要 DEEPSEEK_API_KEY 环境变量，否则跳过。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import pytest

from app import split_user_question

NEEDS_API_KEY = pytest.mark.skipif(
    not os.getenv("DEEPSEEK_API_KEY"),
    reason="需要 DEEPSEEK_API_KEY",
)


def validate_segments(segments, prompt_name):
    """验证子问题结构"""
    errors = []
    if not segments:
        return [f"[FAIL] {prompt_name}: 返回 None"]

    if not isinstance(segments, list):
        return [f"[FAIL] {prompt_name}: 返回值不是列表"]

    if len(segments) < 2:
        errors.append(f"[FAIL] {prompt_name}: 子问题数={len(segments)}，期望 >= 2")

    if len(segments) > 4:
        errors.append(f"[WARN] {prompt_name}: 子问题数={len(segments)}，略微超过 4")

    for i, seg in enumerate(segments):
        if "id" not in seg:
            errors.append(f"[FAIL] {prompt_name}: 第{i}个缺少 id")
        if "prompt" not in seg:
            errors.append(f"[FAIL] {prompt_name}: 第{i}个缺少 prompt")
        elif len(seg["prompt"]) < 5:
            errors.append(f"[FAIL] {prompt_name}: 第{i}个 prompt 太短: {seg['prompt']}")
        if "contextHint" not in seg:
            errors.append(f"[WARN] {prompt_name}: 第{i}个缺少 contextHint")

    return errors


TEST_CASES = [
    "实现一个用户认证系统，包含注册、登录、密码重置功能",
    "为我的博客网站添加评论功能和点赞功能",
    "写一个 Python 脚本来批量重命名文件",
    "给 ShoppingCart 类添加 add_item, remove_item, checkout 方法",
]


@pytest.mark.parametrize("prompt", TEST_CASES)
@NEEDS_API_KEY
def test_split_question(prompt):
    """验证问题能正确拆分为子问题"""
    segments = split_user_question(prompt, None)
    errors = validate_segments(segments, prompt[:30])
    assert not errors, "\n".join(errors)
