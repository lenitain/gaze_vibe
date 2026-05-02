import os
import sys
import json
from dotenv import load_dotenv
import openai

load_dotenv()

client = openai.OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)

def split_user_question(prompt, context_files=None, max_sub_questions=4):
    context_text = ""
    if context_files:
        for f in context_files:
            context_text += f"\n文件 {f['path']}:\n{f['content']}\n"

    split_system = f"""你是一个任务规划助手。用户的编程问题需要从多个角度回答。
请将用户的问题拆成 2-{max_sub_questions} 个独立子问题。

要求:
1. 每个子问题专注一个具体方面
2. 每个子问题的 AI 回答应较短（不超过 20 行代码 + 5 行说明）
3. 子问题之间保持逻辑顺序
4. 不要遗漏重要方面
5. 每个子问题应该是独立的、可回答的
6. 用中文输出 contextHint

输出 JSON 格式（只输出 JSON，不要其他文字）:
[
  {{"id": "1", "prompt": "请实现...", "contextHint": "核心函数", "dependsOn": ""}},
  {{"id": "2", "prompt": "请添加...", "contextHint": "边界处理", "dependsOn": "1"}}
]"""

    try:
        full_prompt = prompt
        if context_text:
            full_prompt = f"项目上下文:\n{context_text}\n\n用户问题:\n{prompt}"

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": split_system},
                {"role": "user", "content": full_prompt},
            ],
            temperature=0.3,
            max_tokens=2000,
        )
        raw = response.choices[0].message.content.strip()
        import re
        json_match = re.search(r"\[[\s\S]*\]", raw)
        if json_match:
            result = json.loads(json_match.group())
            return result[:max_sub_questions]
        return None
    except Exception as e:
        print(f"  拆分失败: {e}")
        return None


def validate_segments(segments, prompt_name):
    errors = []
    if not segments:
        return [f"[FAIL] {prompt_name}: 返回 None，没有拆分子问题"]

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

    if not errors:
        print(f"  [OK] {prompt_name}: {len(segments)} 个子问题")
        for s in segments:
            hint = s.get("contextHint", "?")
            p = s["prompt"][:60]
            print(f"       [{s['id']}] {hint}: {p}...")
    else:
        for e in errors:
            print(f"  {e}")
        # Also show what we got for debugging
        print(f"  raw: {json.dumps(segments, ensure_ascii=False, indent=2)[:500]}")

    return errors


test_prompts = [
    "实现一个用户认证系统，包含注册、登录、密码重置功能",
    "为我的博客网站添加评论功能和点赞功能",
    "写一个 Python 脚本来批量重命名文件",
    "给 ShoppingCart 类添加 add_item, remove_item, checkout 方法",
]

all_passed = True
for p in test_prompts:
    print(f"\n{'='*60}")
    print(f"测试: {p}")
    print(f"{'='*60}")
    segments = split_user_question(p)
    errors = validate_segments(segments, p[:30])
    if errors:
        all_passed = False

print(f"\n{'='*60}")
if all_passed:
    print("所有测试通过 ✓")
else:
    print("部分测试失败 ✗")
    sys.exit(1)
