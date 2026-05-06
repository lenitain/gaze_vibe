"""
GazeVibe 后端服务

集成眼动数据处理器，实现：
1. 实时调整：基于当前轮次眼动数据调整回答风格
2. 长期建模：使用 EMA 平滑用户偏好
3. 详细日志：输出类似 LLM 的思考过程

Prompt 管理：所有 system prompt 存放在 backend/prompts/ 目录，
通过 prompts 模块统一加载（参考 pi-mono .pi/prompts/ 模式）。
"""

import os
import re
import json
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import openai

from config import ALPHA
from eye_tracker_processor import EyeTrackerProcessor, print_thoughts
from errors import APIError, register_error_handlers
from prompts import load_prompt

load_dotenv()

app = Flask(__name__)
CORS(app)
register_error_handlers(app)

# 配置 DeepSeek API (兼容 OpenAI 格式)
client = openai.OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY", "your-api-key-here"),
    base_url="https://api.deepseek.com",
)

# 全局眼动数据处理器
eye_processor = EyeTrackerProcessor()


def adjust_system_prompt(base_prompt: str, adjustments: dict) -> str:
    """
    根据眼动调整参数修改 system prompt

    Args:
        base_prompt: 基础 prompt（从 prompts/ 加载）
        adjustments: 调整参数 (detail_score, explanation_score)

    Returns:
        添加了偏好调整指令的 prompt
    """
    detail = adjustments["detail_score"]
    explanation = adjustments["explanation_score"]

    notes = []

    if detail > 0.55:
        strength = "更" if detail < 0.65 else "明显"
        notes.append(f"用户偏好详细解答，请提供{strength}完整的解释和示例")
    elif detail < 0.45:
        strength = "更" if detail > 0.35 else "明显"
        notes.append(f"用户偏好简洁解答，请{strength}精简解释，直接给核心代码")

    if explanation > 0.55:
        strength = "适当" if explanation < 0.65 else "多"
        notes.append(f"用户喜欢原理性解释，请{strength}增加设计思路和原理解释")
    elif explanation < 0.45:
        strength = "适当" if explanation > 0.35 else "尽量"
        notes.append(f"用户喜欢直接看代码，请{strength}减少文字解释，代码优先")

    if not notes:
        return base_prompt

    adjustment_text = "\n\n[用户偏好调整]\n" + "\n".join(f"- {note}" for note in notes)
    return base_prompt + adjustment_text


def build_context_text(context_files: list[dict] | None) -> str:
    """构建项目文件上下文字符串"""
    if not context_files:
        return ""
    parts = ["\n\n## 项目文件上下文\n\n"]
    for file in context_files:
        lang = file.get("lang", "")
        parts.append(f"### {file['path']}\n\n```{lang}\n{file['content']}\n```\n\n")
    parts.append("请基于以上项目代码上下文回答用户的问题。\n")
    return "".join(parts)


def generate_dual_answers(prompt, context_files=None, eye_data=None):
    """
    生成两个不同风格的答案

    Args:
        prompt: 用户问题
        context_files: 项目文件上下文
        eye_data: 眼动数据 (可选)

    Returns:
        dict: 包含 answerA, answerB, eye_processing 等
    """
    print("\n" + "─" * 60)
    print(f"  收到用户问题: {prompt[:50]}...")
    print("─" * 60)

    # 处理眼动数据
    eye_result = None
    adjustments = {"detail_score": 0.5, "explanation_score": 0.5}

    if eye_data:
        print("\n  检测到眼动数据，开始处理...")
        eye_result = eye_processor.process(eye_data)
        print_thoughts(eye_result["thoughts"])

        if eye_result["valid"]:
            current = eye_result.get("current_scores", {})
            adjustments = {
                "detail_score": current.get("detail_score", eye_result["detail_score"]),
                "explanation_score": current.get(
                    "explanation_score", eye_result["explanation_score"]
                ),
            }
            print(f"\n  调整参数:")
            print(f"    detail_score = {adjustments['detail_score']:.4f}")
            print(f"    explanation_score = {adjustments['explanation_score']:.4f}")
    else:
        print("\n  无眼动数据，使用默认参数")

    # 从 prompts/ 目录加载 system prompts
    system_a = load_prompt("system_a")
    system_b = load_prompt("system_b")

    context_text = build_context_text(context_files)
    system_a += context_text
    system_b += context_text

    # 根据眼动调整参数修改 prompt
    system_a = adjust_system_prompt(system_a, adjustments)
    system_b = adjust_system_prompt(system_b, adjustments)

    if adjustments["detail_score"] != 0.5 or adjustments["explanation_score"] != 0.5:
        print("\n  Prompt 已根据用户偏好调整")
        if adjustments["detail_score"] > 0.6:
            print("    → 详细解答 prompt: 增加详细程度指令")
        elif adjustments["detail_score"] < 0.4:
            print("    → 简洁解答 prompt: 增加简洁程度指令")

    try:
        print("\n  调用 DeepSeek API...")

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
        print(f"    ✓ 详细解答生成完成 ({len(answer_a)} 字符)")

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
        print(f"    ✓ 简洁解答生成完成 ({len(answer_b)} 字符)")

        result = {
            "answerA": answer_a,
            "answerB": answer_b,
            "success": True,
            "adjustments": adjustments,
        }

        if eye_result:
            result["eyeProcessing"] = {
                "valid": eye_result["valid"],
                "detail_score": eye_result.get("detail_score", 0.5),
                "explanation_score": eye_result.get("explanation_score", 0.5),
            }

        print("\n  回答生成完成 ✓")
        return result

    except Exception as e:
        print(f"\n  API 调用失败: {e}")
        return {
            "answerA": f"生成答案A失败: {str(e)}",
            "answerB": f"生成答案B失败: {str(e)}",
            "success": False,
            "error": str(e),
        }


def split_user_question(prompt, context_files, max_sub_questions=4):
    """
    把用户问题拆成多个子问题。
    返回 [{id: str, prompt: str, contextHint: str, dependsOn: str}, ...]
    失败时返回 None
    """
    context_text = ""
    if context_files:
        for f in context_files:
            context_text += f"\n文件 {f['path']}:\n{f['content']}\n"

    # 从 prompts/ 加载分割系统 prompt
    split_system = load_prompt("system_split", {"max_sub_questions": max_sub_questions})

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
        json_match = re.search(r"\[[\s\S]*\]", raw)
        if json_match:
            result = json.loads(json_match.group())
            return result[:max_sub_questions]
        return None
    except Exception as e:
        print(f"问题拆分失败: {e}")
        return None


@app.route("/api/ask", methods=["POST"])
def ask():
    """处理用户的提问 — SSE 分段推送"""
    data = request.json
    prompt = data.get("prompt", "")
    context_files = data.get("contextFiles", [])
    experiment_mode = data.get("experimentMode", "full")
    eye_data = data.get("eyeData")

    if not prompt:
        raise APIError("请输入问题", 400)

    sub_questions = split_user_question(prompt, context_files)
    if not sub_questions or len(sub_questions) <= 1:
        sub_questions = [{"id": "1", "prompt": prompt, "contextHint": ""}]

    def generate():
        prev_summary = None

        for i, sq in enumerate(sub_questions):
            sub_prompt = sq["prompt"]
            if prev_summary and sq.get("dependsOn"):
                sub_prompt = f"上一步: {prev_summary}\n\n当前: {sub_prompt}"

            full_prompt = f"原始问题: {prompt}\n\n当前子任务: {sub_prompt}"
            result = generate_dual_answers(full_prompt, context_files, eye_data)

            event = {
                "type": "segment",
                "index": i,
                "total": len(sub_questions),
                "id": sq["id"],
                "hint": sq.get("contextHint", ""),
                "answerA": result.get("answerA", ""),
                "answerB": result.get("answerB", ""),
                "success": result.get("success", False),
            }
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

            if result.get("success"):
                preview = result.get("answerB", result.get("answerA", ""))
                prev_summary = preview[:200] + "..." if len(preview) > 200 else preview

        done = {
            "type": "done",
            "experimentMode": experiment_mode,
            "adjustments": eye_processor.get_prompt_adjustments(),
        }
        yield f"data: {json.dumps(done, ensure_ascii=False)}\n\n"

    return Response(generate(), mimetype="text/event-stream")


@app.route("/api/preference", methods=["POST"])
def save_preference():
    """保存用户的偏好数据"""
    data = request.json
    preference = data.get("preference", {})
    experiment_mode = data.get("experimentMode", "full")
    eye_metrics = data.get("eyeMetrics")
    answer_a_length = data.get("answerALength", 0)
    answer_b_length = data.get("answerBLength", 0)

    processed_scores = None
    if eye_metrics:
        eye_data_for_process = {
            "timeOnA": preference.get("timeOnA", 0),
            "timeOnB": preference.get("timeOnB", 0),
            "leftToRight": preference.get("leftToRight", 0),
            "rightToLeft": preference.get("rightToLeft", 0),
            "answerALength": answer_a_length,
            "answerBLength": answer_b_length,
            **eye_metrics,
        }
        eye_result = eye_processor.process(eye_data_for_process)
        print_thoughts(eye_result["thoughts"])

        if eye_result.get("valid"):
            processed_scores = eye_result.get("current_scores", {})

    experiment_data = {
        "experimentMode": experiment_mode,
        "preference": preference,
        "eyeMetrics": eye_metrics,
        "answerALength": answer_a_length,
        "answerBLength": answer_b_length,
        "adjustments": eye_processor.get_prompt_adjustments(),
        "processedScores": processed_scores,
        "timestamp": datetime.now().isoformat(),
    }

    experiment_file = "experiment_data.jsonl"
    try:
        with open(experiment_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(experiment_data, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"保存实验数据失败: {e}")

    print("\n" + "─" * 60)
    print("  用户偏好数据")
    print("─" * 60)
    print(f"  实验模式: {experiment_mode}")
    print(f"  最终选择: {preference.get('finalChoice', '未选择')}")
    print(f"  详细区域时长: {preference.get('timeOnA', 0)}ms")
    print(f"  简洁区域时长: {preference.get('timeOnB', 0)}ms")
    print(f"  左→右切换: {preference.get('leftToRight', 0)} 次")
    print(f"  右→左切换: {preference.get('rightToLeft', 0)} 次")

    adjustments = eye_processor.get_prompt_adjustments()
    print(f"\n  长期模型状态:")
    print(f"    累计轮次: {adjustments['round_count']}")
    print(f"    详细程度偏好: {adjustments['detail_score']:.4f}")
    print(f"    解释/代码偏好: {adjustments['explanation_score']:.4f}")
    print("─" * 60 + "\n")

    return jsonify({"success": True})


@app.route("/api/eye-model", methods=["GET"])
def get_eye_model():
    """获取眼动模型状态 (用于调试)"""
    return jsonify(eye_processor.to_dict())


@app.route("/api/eye-model/reset", methods=["POST"])
def reset_eye_model():
    """重置眼动模型"""
    global eye_processor
    eye_processor = EyeTrackerProcessor()
    print("\n  眼动模型已重置\n")
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
            "eye_model_rounds": eye_processor.round_count,
        }
    )


if __name__ == "__main__":
    print("=" * 60)
    print("  GazeVibe 后端服务启动中...")
    print("=" * 60)
    print(
        f"  DeepSeek API Key: {'已配置' if client.api_key and client.api_key != 'your-api-key-here' else '未配置'}"
    )
    print(f"  眼动模型: 已初始化 (EMA α = {ALPHA})")
    print(f"  访问 http://localhost:8000/api/health 检查状态")
    print("=" * 60)
    app.run(host="0.0.0.0", port=8000, debug=True, use_reloader=False)
