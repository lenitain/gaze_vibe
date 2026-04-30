"""
GazeVibe 后端服务

集成眼动数据处理器，实现：
1. 实时调整：基于当前轮次眼动数据调整回答风格
2. 长期建模：使用 EMA 平滑用户偏好
3. 详细日志：输出类似 LLM 的思考过程
"""

import os
import re
import json
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import openai

from eye_tracker_processor import EyeTrackerProcessor, print_thoughts
from code_refactor import refactor_large_code, should_refactor

load_dotenv()

app = Flask(__name__)
CORS(app)

# 配置 DeepSeek API (兼容 OpenAI 格式)
client = openai.OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY", "your-api-key-here"),
    base_url="https://api.deepseek.com",
)

# 全局眼动数据处理器
eye_processor = EyeTrackerProcessor()


def adjust_system_prompt(base_prompt: str, adjustments: dict, prompt_type: str) -> str:
    """
    根据调整参数修改 system prompt

    Args:
        base_prompt: 基础 prompt
        adjustments: 调整参数 (detail_score, explanation_score)
        prompt_type: "detailed" 或 "concise"
    """
    detail = adjustments["detail_score"]
    explanation = adjustments["explanation_score"]

    adjustment_notes = []

    # 详细程度调整（连续梯度，偏离 0.5 即有微调）
    if detail > 0.55:
        strength = "更" if detail < 0.65 else "明显"
        adjustment_notes.append(f"用户偏好详细解答，请提供{strength}完整的解释和示例")
    elif detail < 0.45:
        strength = "更" if detail > 0.35 else "明显"
        adjustment_notes.append(
            f"用户偏好简洁解答，请{strength}精简解释，直接给核心代码"
        )

    # 解释 vs 代码调整（连续梯度）
    if explanation > 0.55:
        strength = "适当" if explanation < 0.65 else "多"
        adjustment_notes.append(
            f"用户喜欢原理性解释，请{strength}增加设计思路和原理解释"
        )
    elif explanation < 0.45:
        strength = "适当" if explanation > 0.35 else "尽量"
        adjustment_notes.append(
            f"用户喜欢直接看代码，请{strength}减少文字解释，代码优先"
        )

    if adjustment_notes:
        adjustment_text = "\n\n[用户偏好调整]\n" + "\n".join(
            f"- {note}" for note in adjustment_notes
        )
        return base_prompt + adjustment_text

    return base_prompt


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
            # 即时调整用原始分数（响应快），长期模型用 EMA
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

    # 构建系统提示词
    system_a = """你是一个注重代码可读性的编程导师。
请输出**注释丰富、讲解详细**的代码：
- 代码中每个关键步骤都添加中文注释，说明为何这样写
- 处理边界情况和错误
- 代码结构清晰，变量命名语义化
- 代码块前给出一两句话的简要说明即可，不要在代码外长篇大论
重点在代码质量，而非文字篇幅。
每次回答代码不超过15行，说明文字不超过3行"""

    system_b = """你是一个追求代码简洁性的编程助手。
请输出**精简干练、无注释**的代码：
- 代码中不写注释，用自解释的变量名和函数名
- 用最短的路径实现功能，合并可简化的逻辑
- 不处理非必要的边缘情况
- 代码块前给出一句话说明即可
重点在代码精简，而非文字篇幅。
每次回答代码不超过15行，说明文字不超过3行"""

    # 添加项目文件上下文
    if context_files:
        context_text = "\n\n## 项目文件上下文\n\n"
        for file in context_files:
            context_text += f"### {file['path']}\n\n```{file.get('lang', '')}\n{file['content']}\n```\n\n"
        context_text += "请基于以上项目代码上下文回答用户的问题。\n"

        system_a += context_text
        system_b += context_text

    # 根据调整参数修改 prompt
    system_a = adjust_system_prompt(system_a, adjustments, "detailed")
    system_b = adjust_system_prompt(system_b, adjustments, "concise")

    # 打印 prompt 调整信息
    if adjustments["detail_score"] != 0.5 or adjustments["explanation_score"] != 0.5:
        print("\n  Prompt 已根据用户偏好调整")
        if adjustments["detail_score"] > 0.6:
            print("    → 详细解答 prompt: 增加详细程度指令")
        elif adjustments["detail_score"] < 0.4:
            print("    → 简洁解答 prompt: 增加简洁程度指令")

    try:
        print("\n  调用 DeepSeek API...")

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
        print(f"    ✓ 详细解答生成完成 ({len(answer_a)} 字符)")

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
        print(f"    ✓ 简洁解答生成完成 ({len(answer_b)} 字符)")

        result = {
            "answerA": answer_a,
            "answerB": answer_b,
            "success": True,
            "adjustments": adjustments,
        }

        # 添加眼动处理结果
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


def estimate_lines(text):
    """估算回答渲染行数，返回总渲染高度(px)，行高按17px算"""
    if not text:
        return 0
    total_lines = 0
    for match in re.finditer(r"```[^\n]*\n([\s\S]*?)```", text):
        block = match.group(1)
        total_lines += len(block.strip().split("\n")) + 2  # +2 for padding

    # 处理代码块外的文本
    parts = re.split(r"```[^\n]*\n[\s\S]*?```", text)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        for line in part.split("\n"):
            line = line.strip()
            if not line:
                total_lines += 1
                continue
            # 中文按35字/行，英文按80字/行
            cn_chars = len(re.findall(r"[\u4e00-\u9fff]", line))
            en_chars = len(line) - cn_chars
            cn_lines = max(1, -(-cn_chars // 35))  # ceil division
            en_lines = max(1, -(-en_chars // 80))
            total_lines += max(cn_lines, en_lines)

    return total_lines * 17


def generate_single_answer(prompt, context_files=None):
    """单次调用，返回 {answerA, answerB, success}"""
    system_a = """你是一个注重代码可读性的编程导师。
请输出**注释丰富、讲解详细**的代码：
- 代码中每个关键步骤都添加中文注释，说明为何这样写
- 处理边界情况和错误
- 代码结构清晰，变量命名语义化
- 代码块前给出一两句话的简要说明即可，不要在代码外长篇大论
重点在代码质量，而非文字篇幅。
每次回答代码不超过15行，说明文字不超过3行"""

    system_b = """你是一个追求代码简洁性的编程助手。
请输出**精简干练、无注释**的代码：
- 代码中不写注释，用自解释的变量名和函数名
- 用最短的路径实现功能，合并可简化的逻辑
- 不处理非必要的边缘情况
- 代码块前给出一句话说明即可
重点在代码精简，而非文字篇幅。
每次回答代码不超过15行，说明文字不超过3行"""

    if context_files:
        context_text = "\n\n## 项目文件上下文\n\n"
        for file in context_files:
            context_text += f"### {file['path']}\n\n```{file.get('lang', '')}\n{file['content']}\n```\n\n"
        context_text += "请基于以上项目代码上下文回答用户的问题。\n"
        system_a += context_text
        system_b += context_text

    try:
        response_a = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_a},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=1200,
        )
        answer_a = response_a.choices[0].message.content

        response_b = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_b},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=1200,
        )
        answer_b = response_b.choices[0].message.content

        return {"answerA": answer_a, "answerB": answer_b, "success": True}
    except Exception as e:
        return {
            "answerA": f"生成失败: {str(e)}",
            "answerB": f"生成失败: {str(e)}",
            "success": False,
            "error": str(e),
        }


def call_ai_to_split(answer, max_lines):
    """调AI把长回答拆成子任务"""
    max_code_lines = max(5, int(max_lines * 0.6))
    max_text_lines = max(3, int(max_lines * 0.4))

    split_system = f"""你是一个任务拆分助手。以下是一个编程问题的完整回答，但它太长了。
请将其拆分成多个独立的小任务，使得每个小任务的AI回答都能控制在指定行数内。

要求：
1. 每个小任务独立可答，有明确的代码输出
2. 小任务之间如果有依赖，标记 dependsOn
3. 每个任务的回答不超过 {max_code_lines} 行代码 + {max_text_lines} 行说明文字
4. 保持原回答的完整性，不要遗漏内容

输出JSON格式：
[
  {{"id": "1", "prompt": "请实现...", "contextHint": "核心函数", "dependsOn": ""}},
  {{"id": "2", "prompt": "请添加...", "contextHint": "边界处理", "dependsOn": "1"}}
]"""

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": split_system},
                {"role": "user", "content": f"请拆分以下回答：\n\n{answer}"},
            ],
            temperature=0.3,
            max_tokens=3000,
        )
        raw = response.choices[0].message.content.strip()
        # 提取JSON
        json_match = re.search(r"\[[\s\S]*\]", raw)
        if json_match:
            tasks = json.loads(json_match.group())
            return tasks
        return []
    except Exception as e:
        print(f"拆分失败: {e}")
        return []


def recursive_split_answer(prompt, context_files, max_lines, depth=0):
    """递归拆分回答"""
    if depth > 3:
        return [generate_single_answer(prompt, context_files)]

    answer = generate_single_answer(prompt, context_files)

    if not answer.get("success"):
        return [answer]

    # 取较长的回答估算
    text_a = answer.get("answerA", "")
    text_b = answer.get("answerB", "")
    estimated = max(estimate_lines(text_a), estimate_lines(text_b))

    if estimated <= max_lines:
        return [answer]

    sub_tasks = call_ai_to_split(text_a, max_lines)

    if not sub_tasks:
        return [answer]

    results = []
    for task in sub_tasks:
        sub_prompt = task.get("prompt", "")
        depends_on = task.get("dependsOn", "")
        if depends_on and results:
            last_answer = results[-1].get("answerA", "")
            summary = last_answer[:200] + "..." if len(last_answer) > 200 else last_answer
            sub_prompt = f"前一步结果摘要:\n{summary}\n\n当前任务:\n{sub_prompt}"

        sub_results = recursive_split_answer(
            sub_prompt, context_files, max_lines, depth + 1
        )
        for sr in sub_results:
            sr["hint"] = task.get("contextHint", "")
        results.extend(sub_results)

    return results


@app.route("/api/ask", methods=["POST"])
def ask():
    """处理用户的提问"""
    data = request.json
    prompt = data.get("prompt", "")
    context_files = data.get("contextFiles", [])
    experiment_mode = data.get("experimentMode", "full")
    eye_data = data.get("eyeData")  # 新增：眼动数据

    if not prompt:
        return jsonify({"error": "请输入问题"}), 400

    # 生成答案 (包含眼动数据处理)
    result = generate_dual_answers(prompt, context_files, eye_data)
    result["experimentMode"] = experiment_mode

    return jsonify(result)


@app.route("/api/ask-batch", methods=["POST"])
def ask_batch():
    """批量处理子问题"""
    data = request.json
    sub_questions = data.get("subQuestions", [])
    context_files = data.get("contextFiles", [])
    eye_data = data.get("eyeData")

    if not sub_questions:
        return jsonify({"error": "请提供子问题列表"}), 400

    max_splits = 3
    if len(sub_questions) > max_splits:
        return jsonify({"error": f"最多支持 {max_splits} 个子问题"}), 400

    results = []
    prev_summary = None

    for sq in sub_questions:
        prompt = sq.get("prompt", "")
        if prev_summary and sq.get("dependsOn"):
            prompt = f"前一步结果摘要:\n{prev_summary}\n\n当前任务:\n{prompt}"

        is_refactor = sq.get("isRefactor", False)
        if is_refactor:
            code_match = re.search(r"```\w*\n([\s\S]*?)```", prompt)
            if code_match:
                code_block = code_match.group(1)
                if should_refactor(code_block):
                    refactored = refactor_large_code(code_block, context_files)
                    if refactored:
                        results.append(
                            {
                                "id": sq.get("id", ""),
                                "answerA": refactored,
                                "answerB": refactored,
                                "success": True,
                            }
                        )
                        prev_summary = f"代码已重构为多个小函数"
                        continue

        result = generate_dual_answers(prompt, context_files, eye_data)
        results.append(
            {
                "id": sq.get("id", ""),
                "answerA": result.get("answerA", ""),
                "answerB": result.get("answerB", ""),
                "success": result.get("success", False),
            }
        )

        if result.get("success"):
            answer_text = result.get("answerB", result.get("answerA", ""))
            prev_summary = answer_text[:200] + "..." if len(answer_text) > 200 else answer_text

    return jsonify({"results": results, "success": True})


@app.route("/api/ask-v2", methods=["POST"])
def ask_v2():
    """递归拆分 + SSE 流式返回"""
    data = request.json
    prompt = data.get("prompt", "")
    context_files = data.get("contextFiles", [])
    viewport_height = data.get("viewportHeight", 600)

    if not prompt:
        return jsonify({"error": "请输入问题"}), 400

    max_lines = max(5, int(viewport_height / 17))

    def generate():
        try:
            sub_results = recursive_split_answer(prompt, context_files, max_lines)
            total = len(sub_results)

            for i, result in enumerate(sub_results):
                chunk = {
                    "index": i,
                    "total": total,
                    "answerA": result.get("answerA", ""),
                    "answerB": result.get("answerB", ""),
                    "hint": result.get("hint", ""),
                }
                yield f"event: chunk\ndata: {json.dumps(chunk, ensure_ascii=False)}\n\n"

            yield f"event: done\ndata: {json.dumps({'success': True})}\n\n"

        except Exception as e:
            error_data = {"success": False, "error": str(e)}
            yield f"event: done\ndata: {json.dumps(error_data)}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.route("/api/preference", methods=["POST"])
def save_preference():
    """保存用户的偏好数据"""
    data = request.json
    preference = data.get("preference", {})
    experiment_mode = data.get("experimentMode", "full")
    eye_metrics = data.get("eyeMetrics")  # 新增：详细眼动指标
    answer_a_length = data.get("answerALength", 0)
    answer_b_length = data.get("answerBLength", 0)

    # 先处理眼动数据 (6步处理)，再保存（确保adjustments是最新的）
    processed_scores = None
    if eye_metrics:
        # 合并 preference 中的时间数据到眼动指标
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

        # 提取处理后的中间指标
        if eye_result.get("valid"):
            processed_scores = eye_result.get("current_scores", {})

    # 记录实验数据（在处理之后，确保adjustments是最新的）
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

    # 保存到实验数据文件
    experiment_file = "experiment_data.jsonl"
    try:
        with open(experiment_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(experiment_data, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"保存实验数据失败: {e}")

    # 打印偏好数据摘要
    print("\n" + "─" * 60)
    print("  用户偏好数据")
    print("─" * 60)
    print(f"  实验模式: {experiment_mode}")
    print(f"  最终选择: {preference.get('finalChoice', '未选择')}")
    print(f"  详细区域时长: {preference.get('timeOnA', 0)}ms")
    print(f"  简洁区域时长: {preference.get('timeOnB', 0)}ms")
    print(f"  左→右切换: {preference.get('leftToRight', 0)} 次")
    print(f"  右→左切换: {preference.get('rightToLeft', 0)} 次")

    # 打印长期模型状态
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
    print(f"  眼动模型: 已初始化 (EMA α = {EyeTrackerProcessor.ALPHA})")
    print(f"  访问 http://localhost:8000/api/health 检查状态")
    print("=" * 60)
    app.run(host="0.0.0.0", port=8000, debug=True, use_reloader=False)
