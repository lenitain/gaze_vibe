"""
GazeVibe 后端服务
"""

import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
import openai

app = Flask(__name__)
CORS(app)

# 配置 OpenAI API
openai.api_key = os.getenv("OPENAI_API_KEY", "your-api-key-here")

# 可选：配置其他 LLM
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")


def generate_dual_answers(prompt, preference=None):
    """
    生成两个不同风格的答案
    - answerA: 详细解释风格
    - answerB: 简洁代码风格
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
用户需要简洁、直接的答案。
请只给出关键信息：
- 最少的必要解释
- 直接可用的代码
- 如果有多种方案，只给出最好的那个"""

    # 如果有用户偏好，调整回答策略
    if preference:
        if preference.get("finalChoice") == "A":
            system_b += "\n注意：用户之前选择了详细解答，说明用户偏好详细解释风格。"
        elif preference.get("finalChoice") == "B":
            system_a += "\n注意：用户之前选择了简洁解答，说明用户偏好简洁直接的风格。"

        # 根据阅读时间调整
        time_a = preference.get("timeOnA", 0)
        time_b = preference.get("timeOnB", 0)

        if time_a > time_b * 1.5:
            system_b += "\n注意：用户在详细解答上停留更久，可以适当增加一些解释。"
        elif time_b > time_a * 1.5:
            system_a += "\n注意：用户在简洁解答上停留更久，回答可以更精简。"

    try:
        # 生成详细答案
        response_a = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_a},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=2000,
        )
        answer_a = response_a.choices[0].message.content

        # 生成简洁答案
        response_b = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_b},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=500,
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

    if not prompt:
        return jsonify({"error": "请输入问题"}), 400

    result = generate_dual_answers(prompt, preference)
    return jsonify(result)


@app.route("/api/preference", methods=["POST"])
def save_preference():
    """保存用户的偏好数据"""
    data = request.json
    preference = data.get("preference", {})

    # 可以保存到文件或数据库
    # 这里简单打印
    print("用户偏好数据:", json.dumps(preference, indent=2))

    return jsonify({"success": True})


@app.route("/api/health", methods=["GET"])
def health():
    """健康检查"""
    return jsonify(
        {
            "status": "ok",
            "openai_configured": bool(
                openai.api_key and openai.api_key != "your-api-key-here"
            ),
        }
    )


if __name__ == "__main__":
    print("=" * 50)
    print("GazeVibe 后端服务启动中...")
    print("=" * 50)
    print(
        f"OpenAI API Key: {'已配置' if openai.api_key and openai.api_key != 'your-api-key-here' else '未配置'}"
    )
    print("访问 http://localhost:8000/api/health 检查状态")
    print("=" * 50)
    app.run(host="0.0.0.0", port=8000, debug=True)
