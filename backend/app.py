"""
GazeVibe 后端服务
"""

import os
import json
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS
import openai

load_dotenv()

app = Flask(__name__)
CORS(app)

# 配置 DeepSeek API (兼容 OpenAI 格式)
client = openai.OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY", "your-api-key-here"),
    base_url="https://api.deepseek.com",
)


def generate_dual_answers(prompt, context_files=None):
    """
    生成两个不同风格的答案
    - answerA: 详细解释风格
    - answerB: 简洁代码风格
    - context_files: 项目文件上下文
    """

    # 构建系统提示词
    system_a = """你是一个耐心的编程导师。
用户需要你给出详细、完整的解答，包括：
- 问题分析
- 解决思路
- 完整代码
- 代码解释
请尽可能详细地解释每个部分。"""

    system_b = """你是一个高效的编程助手。
用户需要简洁、直接的答案。请遵循：
- 给出简短的解释，说明你做了什么修改
- 给出修改后的完整代码，不要原封不动地输出原始文件
- 如果有多种方案，只给出最好的那个
- 不要只输出代码块，前面必须有文字说明"""

    # 添加项目文件上下文
    if context_files:
        context_text = "\n\n## 项目文件上下文\n\n"
        for file in context_files:
            context_text += f"### {file['path']}\n\n```{file.get('lang', '')}\n{file['content']}\n```\n\n"
        context_text += "请基于以上项目代码上下文回答用户的问题。\n"

        system_a += context_text
        system_b += context_text

    try:
        # 生成详细答案
        response_a = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_a},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=3000,
        )
        answer_a = response_a.choices[0].message.content

        # 生成简洁答案
        response_b = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_b},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=3000,
        )
        answer_b = response_b.choices[0].message.content

        return {"answerA": answer_a, "answerB": answer_b, "success": True}

    except Exception as e:
        return {
            "answerA": f"生成答案A失败: {str(e)}",
            "answerB": f"生成答案B失败: {str(e)}",
            "success": False,
            "error": str(e),
        }


@app.route("/api/ask", methods=["POST"])
def ask():
    """处理用户的提问"""
    data = request.json
    prompt = data.get("prompt", "")
    preference = data.get("preference", {})
    context_files = data.get("contextFiles", [])
    experiment_mode = data.get("experimentMode", "treatment")

    if not prompt:
        return jsonify({"error": "请输入问题"}), 400

    # preference 不再影响回答生成（仅用于实验数据记录）
    result = generate_dual_answers(prompt, context_files)
    result["experimentMode"] = experiment_mode
    return jsonify(result)


@app.route("/api/preference", methods=["POST"])
def save_preference():
    """保存用户的偏好数据"""
    data = request.json
    preference = data.get("preference", {})
    experiment_mode = data.get("experimentMode", "treatment")

    # 记录实验数据
    experiment_data = {
        "experimentMode": experiment_mode,
        "preference": preference,
        "timestamp": __import__("datetime").datetime.now().isoformat(),
    }

    # 保存到实验数据文件
    experiment_file = "experiment_data.jsonl"
    try:
        with open(experiment_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(experiment_data, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"保存实验数据失败: {e}")

    print("实验数据:", json.dumps(experiment_data, indent=2, ensure_ascii=False))

    return jsonify({"success": True})


@app.route("/api/health", methods=["GET"])
def health():
    """健康检查"""
    return jsonify(
        {
            "status": "ok",
            "deepseek_configured": bool(
                client.api_key and client.api_key != "your-api-key-here"
            ),
        }
    )


if __name__ == "__main__":
    print("=" * 50)
    print("GazeVibe 后端服务启动中...")
    print("=" * 50)
    print(
        f"DeepSeek API Key: {'已配置' if client.api_key and client.api_key != 'your-api-key-here' else '未配置'}"
    )
    print("访问 http://localhost:8000/api/health 检查状态")
    print("=" * 50)
    app.run(host="0.0.0.0", port=8000, debug=True)
