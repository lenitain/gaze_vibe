import os
import openai

client = openai.OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY", "your-api-key-here"),
    base_url="https://api.deepseek.com",
)


def refactor_large_code(code_block, context_files=None):
    if not code_block or len(code_block.strip()) == 0:
        return None

    lines = code_block.strip().split("\n")
    if len(lines) <= 50:
        return None

    context_text = ""
    if context_files:
        context_text = "\n\n## 项目上下文\n\n"
        for file in context_files:
            context_text += f"### {file['path']}\n\n```\n{file['content']}\n```\n\n"

    system_prompt = """你是一个代码重构专家。
请将以下大函数拆分成多个小函数，每个小函数职责单一。
要求：
1. 保持原有功能不变
2. 每个函数命名清晰
3. 提取公共逻辑为独立函数
4. 返回重构后的完整代码

返回格式：
```javascript
// 函数1: xxx
function func1() {}

// 函数2: xxx
function func2() {}
```"""

    if context_files:
        system_prompt += context_text

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"请重构以下代码:\n\n```\n{code_block}\n```",
                },
            ],
            temperature=0.3,
            max_tokens=3000,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"代码重构失败: {e}")
        return None


def should_refactor(code_block):
    if not code_block:
        return False
    lines = code_block.strip().split("\n")
    return len(lines) > 50
