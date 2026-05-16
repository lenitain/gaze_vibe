"""
GazeVibe 后端服务

AI 工程架构：
- LLMClient: 统一 LLM 调用（retry/streaming/token tracking）
- PromptBuilder: 动态 prompt 组装（眼动 + 上下文 + 历史）
- StructuredOutput: 通过 function calling 约束返回格式
- ToolAgent: LLM 通过 tools 直接操作文件
- SSEEvents: 细粒度流式事件协议
- LLMLogger: 调用日志与上下文管理
"""

import json
import os
import re
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request
from flask_cors import CORS

from config import ALPHA, MEMORY_TOP_K
from errors import APIError, register_error_handlers
from eye_tracker_processor import EyeTrackerProcessor, print_thoughts

# === 新架构模块 ===
from llm_client import LLMClient, LLMError
from llm_logger import LLMLogger
from memory.extractor import extract_semantic_memories
from memory.retrieval import format_context, retrieve
from memory.store import MemoryStore
from persona_loader import PersonaLoader
from persona_state import get_persona_bias, get_prompt_scores, initial_state, record_choice
from prompt_builder import build_dual_answer_prompts
from prompts import load_prompt
from sse_events import (
    create_done,
    create_eye_adjustment,
    create_segment_end,
    create_segment_start,
    create_text_delta,
    create_text_end,
)
from vector_utils import init_embedding_client

load_dotenv()

app = Flask(__name__)
CORS(app)
register_error_handlers(app)

# === 初始化 ===

# LLM 客户端 (替代裸 openai client)
llm_client = LLMClient(
    model="deepseek-chat",
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
    max_retries=2,
    timeout=120,
)

# LLM 调用日志
llm_logger = LLMLogger(log_dir="logs")
# 注册回调：每次 LLM 调用自动记录
llm_client.on_record = lambda record: llm_logger.record_from_llm_record(record, caller="generate_dual_answers")

# 全局眼动数据处理器
eye_processor = EyeTrackerProcessor()

# 记忆系统
init_embedding_client(llm_client._client)
memory_store = MemoryStore()


def generate_dual_answers(prompt, context_files=None, eye_data=None, persona_state=None):
    """
    生成两个不同风格的答案

    使用新架构：
    - PromptBuilder 组装 prompt
    - LLMClient.generate() 带 retry
    - SSEEvents 推送眼动状态
    """
    print("\n" + "─" * 60)
    print(f"  收到用户问题: {prompt[:50]}...")
    print("─" * 60)

    # 1. 处理眼动数据
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
                "explanation_score": current.get("explanation_score", eye_result["explanation_score"]),
            }
            print("\n  调整参数:")
            print(f"    detail_score = {adjustments['detail_score']:.4f}")
            print(f"    explanation_score = {adjustments['explanation_score']:.4f}")
    else:
        print("\n  无眼动数据，使用默认参数")

    # 2. 使用 PromptBuilder 组装 prompt（传入动态 Persona）
    if persona_state:
        # 从前端传入的 state dict 构建 Persona 对象
        pa_info = get_prompt_scores(persona_state, "A")
        pb_info = get_prompt_scores(persona_state, "B")
        pa = PersonaLoader.load(pa_info["name"])
        pb = PersonaLoader.load(pb_info["name"])
        for k, v in pa_info["scores"].items():
            pa.scores[k] = v
        for k, v in pb_info["scores"].items():
            pb.scores[k] = v
        persona_a_obj, persona_b_obj = pa, pb
    else:
        persona_a_obj, persona_b_obj = "稳健派", "现代派"

    prompt_a, prompt_b = build_dual_answer_prompts(
        persona_a=persona_a_obj,
        persona_b=persona_b_obj,
        detail_score=adjustments["detail_score"],
        explanation_score=adjustments["explanation_score"],
        confidence=eye_result.get("confidence", None) if eye_result else None,
        context_files=context_files,
    )

    if adjustments["detail_score"] != 0.5 or adjustments["explanation_score"] != 0.5:
        print("\n  Prompt 已根据用户偏好调整")
        if adjustments["detail_score"] > 0.6:
            print("    → 详细解答 prompt: 增加详细程度指令")
        elif adjustments["detail_score"] < 0.4:
            print("    → 简洁解答 prompt: 增加简洁程度指令")

    # 3. 使用 LLMClient 生成（带 retry + 精确 token 统计）
    try:
        print("\n  调用 DeepSeek API (LLMClient)...")

        # 生成 Answer A（详细）
        response_a = llm_client.generate(
            system_prompt=prompt_a,
            user_prompt=prompt,
            temperature=0.7,
            max_tokens=3000,
        )
        answer_a = response_a.text
        print(f"    ✓ 详细解答生成完成 ({len(answer_a)} 字符, {response_a.usage.total_tokens} tokens)")

        # 生成 Answer B（简洁）
        response_b = llm_client.generate(
            system_prompt=prompt_b,
            user_prompt=prompt,
            temperature=0.7,
            max_tokens=3000,
        )
        answer_b = response_b.text
        print(f"    ✓ 简洁解答生成完成 ({len(answer_b)} 字符, {response_b.usage.total_tokens} tokens)")

        result = {
            "answerA": answer_a,
            "answerB": answer_b,
            "success": True,
            "adjustments": adjustments,
            "usage": {
                "a": {"tokens": response_a.usage.total_tokens, "latency_ms": response_a.latency_ms},
                "b": {"tokens": response_b.usage.total_tokens, "latency_ms": response_b.latency_ms},
            },
        }

        if eye_result:
            result["eyeProcessing"] = {
                "valid": eye_result["valid"],
                "detail_score": eye_result.get("detail_score", 0.5),
                "explanation_score": eye_result.get("explanation_score", 0.5),
                "confidence": eye_result.get("confidence", 0),
            }

        print("\n  回答生成完成 ✓")
        return result

    except LLMError as e:
        print(f"\n  API 调用失败 (重试耗尽): {e}")
        return {
            "answerA": f"生成答案A失败: {str(e)}",
            "answerB": f"生成答案B失败: {str(e)}",
            "success": False,
            "error": str(e),
        }
    except Exception as e:
        print(f"\n  未知错误: {e}")
        return {
            "answerA": f"生成答案A失败: {str(e)}",
            "answerB": f"生成答案B失败: {str(e)}",
            "success": False,
            "error": str(e),
        }


def split_user_question(prompt, context_files, max_sub_questions=4):
    """
    使用结构化输出拆解用户问题
    替代当前正则 + JSON 解析的方式
    """
    context_text = ""
    if context_files:
        for f in context_files:
            context_text += f"\n文件 {f['path']}:\n{f['content']}\n"

    split_system = load_prompt("system_split", {"max_sub_questions": max_sub_questions})

    try:
        full_prompt = prompt
        if context_text:
            full_prompt = f"项目上下文:\n{context_text}\n\n用户问题:\n{prompt}"

        # 使用 generate_structured 确保返回合法 JSON
        response = llm_client.generate(
            system_prompt=split_system,
            user_prompt=full_prompt,
            temperature=0.3,
            max_tokens=2000,
        )
        raw = response.text.strip()

        json_match = re.search(r"\[[\s\S]*\]", raw)
        if json_match:
            result = json.loads(json_match.group())
            return result[:max_sub_questions]
        return None
    except Exception as e:
        print(f"问题拆分失败: {e}")
        return None


# ===== API 路由 =====

@app.route("/api/ask", methods=["POST"])
def ask():
    """处理用户的提问 — SSE 分段推送（新事件协议）"""
    data = request.json
    prompt = data.get("prompt", "")
    context_files = data.get("contextFiles", [])
    experiment_mode = data.get("experimentMode", "full")
    eye_data = data.get("eyeData")
    persona_state = data.get("personaState")

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

            # RAG 检索相关记忆
            memory_context = ""
            if memory_store.count() > 0:
                try:
                    results = retrieve(memory_store, sub_prompt, top_k=MEMORY_TOP_K)
                    if results:
                        memory_context = format_context(results)
                        full_prompt = f"{memory_context}\n\n---\n\n{full_prompt}"
                        print(f"    注入 {len(results)} 条记忆上下文")
                except Exception as e:
                    print(f"    记忆检索失败: {e}")

            # SSE: 子问题开始
            yield create_segment_start(i, len(sub_questions), sq["id"], sq.get("contextHint", ""))

            result = generate_dual_answers(full_prompt, context_files, eye_data, persona_state)

            # SSE: 推送眼动状态
            if result.get("eyeProcessing"):
                ep = result["eyeProcessing"]
                yield create_eye_adjustment(
                    detail=ep.get("detail_score", 0.5),
                    explanation=ep.get("explanation_score", 0.5),
                    persona_bias=ep.get("persona_bias", 0.5),
                    confidence=ep.get("confidence", 0),
                    round_count=eye_processor.round_count,
                )

            # SSE: A 文本推送
            answer_a = result.get("answerA", "")
            yield create_text_delta(sq["id"], "detailed", answer_a)
            yield create_text_end(sq["id"], "detailed", answer_a)

            # SSE: B 文本推送
            answer_b = result.get("answerB", "")
            yield create_text_delta(sq["id"], "concise", answer_b)
            yield create_text_end(sq["id"], "concise", answer_b)

            # SSE: 子问题结束
            yield create_segment_end(i, len(sub_questions), sq["id"], result.get("success", False))

            if result.get("success"):
                preview = answer_b[:200] + "..." if len(answer_b) > 200 else answer_b
                prev_summary = preview

        # 提取 semantic 记忆
        if memory_store.count() < 50:
            try:
                best_answer = result.get("answerB", "") or result.get("answerA", "")
                if best_answer and len(best_answer) > 50:
                    added = extract_semantic_memories(memory_store, llm_client, prompt, best_answer)
                    if added:
                        print(f"    提取 {len(added)} 条 semantic 记忆")
            except Exception as e:
                print(f"    语义提取失败: {e}")

        # SSE: 全部完成
        yield create_done(experiment_mode, eye_processor.get_prompt_adjustments())

    return Response(generate(), mimetype="text/event-stream")


@app.route("/api/ask-batch", methods=["POST"])
def ask_batch():
    """批量子问题处理 — 使用 ToolAgent"""
    data = request.json
    prompt = data.get("prompt", "")
    context_files = data.get("contextFiles", [])
    persona_state = data.get("personaState")

    if not prompt:
        raise APIError("请输入问题", 400)

    # 拆分子问题
    sub_questions = split_user_question(prompt, context_files)
    if not sub_questions:
        sub_questions = [{"id": "1", "prompt": prompt, "contextHint": ""}]

    def generate():
        for i, sq in enumerate(sub_questions):
            yield create_segment_start(i, len(sub_questions), sq["id"], sq.get("contextHint", ""))

            result = generate_dual_answers(sq["prompt"], context_files, persona_state=persona_state)
            yield create_text_delta(sq["id"], "detailed", result.get("answerA", ""))
            yield create_text_end(sq["id"], "detailed", result.get("answerA", ""))
            yield create_text_delta(sq["id"], "concise", result.get("answerB", ""))
            yield create_text_end(sq["id"], "concise", result.get("answerB", ""))
            yield create_segment_end(i, len(sub_questions), sq["id"], result.get("success", False))

        yield create_done("batch", {})

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
    persona_state = data.get("personaState")

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
    print("\n  长期模型状态:")
    print(f"    累计轮次: {adjustments['round_count']}")
    print(f"    详细程度偏好: {adjustments['detail_score']:.4f}")
    print(f"    解释/代码偏好: {adjustments['explanation_score']:.4f}")

    # 更新 Persona 状态
    final_choice = preference.get("finalChoice", None)
    updated_state = None
    if final_choice in ("A", "B") and persona_state:
        updated_state = record_choice(persona_state, final_choice)
        persona_gap = get_persona_bias(updated_state)
        print(f"    Persona 偏差: {persona_gap:.4f} (已收敛={updated_state['converged']})")
        if updated_state['converged']:
            print("    Persona 已收敛，未选中侧进入随机探索模式")

        # 保存 episodic 记忆（眼动信号 + 选择）
        try:
            memory_store.add_episodic(
                content=f"用户偏好 Persona {final_choice}（实验模式: {experiment_mode}）",
                persona=final_choice,
                confidence=adjustments.get("persona_bias", 0.5),
                metadata={
                    "detail_score": adjustments.get("detail_score", 0.5),
                    "explanation_score": adjustments.get("explanation_score", 0.5),
                    "experiment_mode": experiment_mode,
                },
            )
            print(f"    保存 episodic 记忆（Persona {final_choice}）")
        except Exception as e:
            print(f"    保存 episodic 记忆失败: {e}")
    else:
        print("    Persona 状态: 未更新（无选择或无传入状态）")

    print("─" * 60 + "\n")

    # 输出 LLM 统计
    print("\n  LLM 调用统计:")
    summary = llm_logger.session_summary()
    print(f"    总调用: {summary['total_calls']}")
    print(f"    成功: {summary['successful']}")
    print(f"    总 Token: {summary['total_tokens']}")
    print(f"    平均延迟: {summary['avg_latency_ms']}ms")
    print("─" * 60 + "\n")

    return jsonify({"success": True, "personaState": updated_state})


@app.route("/api/eye-model", methods=["GET"])
def get_eye_model():
    """获取眼动模型状态 (用于调试)"""
    return jsonify(eye_processor.to_dict())


@app.route("/api/eye-model/reset", methods=["POST"])
def reset_eye_model():
    """重置眼动模型（Persona 状态由前端自行删除）"""
    global eye_processor
    eye_processor = EyeTrackerProcessor()
    memory_store.clear()
    print("\n  眼动模型 + 记忆系统已重置\n")
    return jsonify({"success": True, "initialPersonaState": initial_state()})


@app.route("/api/stats", methods=["GET"])
def get_stats():
    """获取 LLM 调用统计"""
    return jsonify({
        "llm": llm_logger.session_summary(),
        "eye": {
            "round_count": eye_processor.round_count,
            "detail_score": eye_processor.long_term_detail,
            "explanation_score": eye_processor.long_term_explanation,
        },
        "persona": {
            "note": "Persona 状态由前端管理，存储于项目根目录 persona_state.json",
        },
        "memory": {
            "total": memory_store.count(),
            "semantic": memory_store.count("semantic"),
            "episodic": memory_store.count("episodic"),
        },
    })


@app.route("/api/health", methods=["GET"])
def health():
    """健康检查"""
    return jsonify(
        {
            "status": "ok",
            "deepseek_configured": bool(
                llm_client.api_key and llm_client.api_key != "your-api-key-here"
            ),
            "eye_model_rounds": eye_processor.round_count,
            "llm_calls": llm_logger.session_summary()["total_calls"],
        }
    )


if __name__ == "__main__":
    print("=" * 60)
    print("  GazeVibe 后端服务 (AI 工程架构 v2)")
    print("=" * 60)
    print("  LLMClient: deepseek-chat (retry=2, timeout=120s)")
    print("  PromptBuilder: 动态组装 + 眼动调整")
    print(f"  EyeTracker: EMA α = {ALPHA}")
    print(f"  LLMLogger: {llm_logger.log_dir / '*.jsonl'}")
    print("  访问 http://localhost:8000/api/health 检查状态")
    print("  访问 http://localhost:8000/api/stats 查看统计")
    print("=" * 60)
    app.run(host="0.0.0.0", port=8000, debug=True, use_reloader=False)
