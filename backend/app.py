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

from config import (
    ALPHA,
    ANSWER_MAX_TOKENS,
    ANSWER_TEMPERATURE,
    LLM_BASE_URL,
    LLM_MAX_RETRIES,
    LLM_MODEL,
    LLM_TIMEOUT,
    LOG_DIR,
    MEMORY_TOP_K,
    PROJECT_ROOT,
    SPLIT_MAX_TOKENS,
    SPLIT_TEMPERATURE,
)
from errors import APIError, register_error_handlers
from eye_tracker_processor import EyeTrackerProcessor, print_thoughts

# === 新架构模块 ===
from llm_client import LLMClient, LLMError
from llm_logger import LLMLogger
from agent_loop import AgentLoop
from memory.extractor import extract_semantic_memories
from memory.retrieval import format_context, retrieve
from memory.store import MemoryStore
from persona_loader import DIMENSION_DESCRIPTIONS, DIMENSION_PRIORITY, PersonaLoader
from persona_state import (
    classify_dimensions,
    get_persona_bias,
    get_prompt_scores,
    load_state,
    log_state_change,
    record_choice,
    reset_state,
    save_state,
)
from session import Session, SessionState
from storage import MemoryStorage
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
    model=LLM_MODEL,
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=LLM_BASE_URL,
    max_retries=LLM_MAX_RETRIES,
    timeout=LLM_TIMEOUT,
)

# LLM 调用日志
llm_logger = LLMLogger(log_dir=LOG_DIR)
# 注册回调：每次 LLM 调用自动记录
llm_client.on_record = lambda record: llm_logger.record_from_llm_record(record, caller="generate_dual_answers")

# 全局存储后端（纯内存，进程退出即清空）
eye_storage = MemoryStorage[dict]()
memory_storage = MemoryStorage[list]()
session_storage = MemoryStorage[SessionState]()

# 项目根目录映射（前端可通过 API 设置，优先级高于环境变量）
_project_root_map: dict[str, str] = {}

# 全局眼动数据处理器（带 Storage 持久化）
eye_processor = EyeTrackerProcessor(storage=eye_storage, storage_key="default")

# 记忆系统
init_embedding_client(llm_client._client)
_memory_stores: dict[str, "MemoryStore"] = {}


def _get_memory(project_name: str) -> "MemoryStore":
    """获取项目的 MemoryStore，按需创建（使用全局 memory_storage）"""
    if project_name not in _memory_stores:
        _memory_stores[project_name] = MemoryStore(project_name, storage=memory_storage)
    return _memory_stores[project_name]


def _get_session(project_name: str = "default") -> "Session":
    """获取项目的 Session，按需创建"""
    return Session(session_storage, project_name)


def generate_dual_answers(prompt, context_files=None, eye_data=None, persona_state=None, project_root=None):
    """
    生成两个不同风格的答案

    使用新架构：
    - PromptBuilder 组装 prompt
    - AgentLoop（有 project_root 时）或 LLMClient.generate()（无工具时）
    - SSEEvents 推送眼动状态

    Args:
        prompt: 用户问题
        context_files: 上下文文件列表
        eye_data: 眼动数据
        persona_state: Persona 状态
        project_root: 项目根目录（提供时启用 AgentLoop + 文件工具）
    """
    print("\n" + "─" * 60)
    # 完整显示用户问题，不截断
    # 如果 prompt 包含记忆上下文（以 "##" 开头），分开显示
    lines = prompt.split("\n")
    question_part = [l for l in lines if l.startswith("原始问题:") or l.startswith("当前子任务:")]
    if question_part:
        print(f"  用户问题: {question_part[-1]}")
        # 显示记忆上下文摘要（不截断内容本身）
        memory_lines = [l for l in lines if l.startswith("##") or l.startswith("- ")]
        if memory_lines:
            for ml in memory_lines[:6]:
                print(f"  {ml}")
            if len(memory_lines) > 6:
                print(f"  ... 共 {len(memory_lines)} 条记忆")
    else:
        print(f"  用户问题: {prompt}")
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

    # 3. 判断是否启用 AgentLoop（有项目根目录时）
    use_agent = project_root is not None and project_root.strip() != ""

    if use_agent:
        from tool import default_tools
        tools = default_tools(project_root)
        agent = AgentLoop(llm_client, tools)
        tool_hint = (
            "\n\n[工具说明]\n"
            "你可以使用以下工具操作项目文件：\n"
            "- read_file: 读取项目文件\n"
            "- write_file: 创建/更新文件\n"
            "- search_code: 在项目中搜索代码\n"
            "- list_files: 列出项目目录结构\n"
            "- create_directory: 创建目录\n"
            "请根据需要调用工具完成任务，最后给出清晰的文字总结。"
        )
        prompt_a_with_tools = prompt_a + tool_hint
        prompt_b_with_tools = prompt_b + tool_hint
        print(f"\n  启用 AgentLoop (project_root={project_root})")
    else:
        prompt_a_with_tools = prompt_a
        prompt_b_with_tools = prompt_b
        agent = None
        print("\n  标准模式（无 project_root，直接 LLM 调用）")

    # 4. 生成
    try:
        if use_agent:
            print("\n  调用 AgentLoop（静默执行 tool_calls）...")

            # Answer A
            result_a = agent.run(system_prompt=prompt_a_with_tools, user_prompt=prompt)
            answer_a = result_a.text
            print(f"    ✓ 详细解答生成完成 ({len(answer_a)} 字符, {result_a.turn_count} 轮)")
            if result_a.tool_calls:
                print(f"      中间调用了 {len(result_a.tool_calls)} 次工具")

            # Answer B
            result_b = agent.run(system_prompt=prompt_b_with_tools, user_prompt=prompt)
            answer_b = result_b.text
            print(f"    ✓ 简洁解答生成完成 ({len(answer_b)} 字符, {result_b.turn_count} 轮)")
            if result_b.tool_calls:
                print(f"      中间调用了 {len(result_b.tool_calls)} 次工具")
        else:
            print("\n  调用 DeepSeek API (LLMClient)...")

            # 生成 Answer A（详细）
            response_a = llm_client.generate(
                system_prompt=prompt_a,
                user_prompt=prompt,
                temperature=ANSWER_TEMPERATURE,
                max_tokens=ANSWER_MAX_TOKENS,
            )
            answer_a = response_a.text
            print(f"    ✓ 详细解答生成完成 ({len(answer_a)} 字符, {response_a.usage.total_tokens} tokens)")

            # 生成 Answer B（简洁）
            response_b = llm_client.generate(
                system_prompt=prompt_b,
                user_prompt=prompt,
                temperature=ANSWER_TEMPERATURE,
                max_tokens=ANSWER_MAX_TOKENS,
            )
            answer_b = response_b.text
            print(f"    ✓ 简洁解答生成完成 ({len(answer_b)} 字符, {response_b.usage.total_tokens} tokens)")

        result = {
            "answerA": answer_a,
            "answerB": answer_b,
            "success": True,
            "adjustments": adjustments,
        }

        if use_agent:
            result["usage"] = {
                "a": {"tokens": 0, "latency_ms": 0, "turn_count": result_a.turn_count, "tool_calls": len(result_a.tool_calls)},
                "b": {"tokens": 0, "latency_ms": 0, "turn_count": result_b.turn_count, "tool_calls": len(result_b.tool_calls)},
            }
            result["agent_log"] = {
                "a": result_a.tool_calls,
                "b": result_b.tool_calls,
            }
        else:
            result["usage"] = {
                "a": {"tokens": response_a.usage.total_tokens, "latency_ms": response_a.latency_ms},
                "b": {"tokens": response_b.usage.total_tokens, "latency_ms": response_b.latency_ms},
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
            temperature=SPLIT_TEMPERATURE,
            max_tokens=SPLIT_MAX_TOKENS,
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


# ===== LLM 维度分类 =====

def classify_dimensions_llm(question: str) -> dict | None:
    """
    使用 LLM 判断用户问题涉及哪些维度，并给出推理。

    比关键词匹配更准确，能处理"这个 toml crate 依赖太重了"这种复合语义。

    Returns:
        {
            "dims": ["error_handling", ...],  # 涉及的维度列表
            "reasonings": {                      # 每维度推理
                "error_handling": "用户问题提到了'panic'和'Result'..."
            }
        }
        失败返回 None（由调用方回退到关键词）。
    """
    # 构建维度描述
    dim_parts = []
    for dim in DIMENSION_PRIORITY:
        desc = DIMENSION_DESCRIPTIONS.get(dim, {})
        label = {
            "ecosystem_maturity": "生态成熟度",
            "correctness_strategy": "正确性策略",
            "naming_style": "命名风格",
            "documentation_depth": "文档深度",
            "error_handling": "错误处理",
            "edge_case_coverage": "边界覆盖",
            "dependency_philosophy": "依赖哲学",
            "abstraction_timing": "抽象时机",
            "testing_strategy": "测试策略",
            "performance_priority": "性能优先级",
        }.get(dim, dim)
        extremes = f"{desc.get(1, '')} ↔ {desc.get(5, '')}" if desc else ""
        dim_parts.append(f"- {label} ({dim}): {extremes}")

    dim_descriptions = "\n".join(dim_parts)

    system_prompt = f"""你是一个编程问题维度分析器。

用户会输入一个编程问题，你需要判断它涉及以下哪些维度（可多选）：

{dim_descriptions}

对每个涉及的维度，解释为什么用户的问题与该维度相关，以及用户在该维度上可能偏向哪一侧（稳健极5/现代极1）。

返回 JSON 格式：
{{
  "dims": ["error_handling"],
  "reasonings": {{
    "error_handling": "用户问题中提到了'panic'和'Result'，属于错误处理范畴。用户询问是否应该用自定义错误类型替代 anyhow，说明用户可能倾向于更严谨的错误处理方式（稳健派，score≈4-5）"
  }}
}}
如果问题不涉及任何特定维度，返回 {{"dims": [], "reasonings": {{}}}}。
只输出 JSON，不要额外解释。"""

    try:
        response = llm_client.generate(
            system_prompt=system_prompt,
            user_prompt=question,
            temperature=0.1,
            max_tokens=300,
        )
        raw = response.text.strip()
        import json
        # 尝试完整解析为 JSON（处理可能的前后噪音）
        # 先找第一个 { 和最后一个 }
        start = raw.find('{')
        end = raw.rfind('}')
        if start != -1 and end != -1 and end > start:
            cleaned = raw[start:end+1]
            result = json.loads(cleaned)
            dims = result.get("dims", [])
            reasonings = result.get("reasonings", {})
            if isinstance(dims, list):
                valid = [d for d in dims if d in DIMENSION_PRIORITY]
                if valid:
                    return {
                        "dims": valid,
                        "reasonings": {d: reasonings.get(d, "") for d in valid}
                    }
    except json.JSONDecodeError as e:
        print(f"    LLM 维度分类 JSON 解析失败: {e}")
        print(f"    LLM 原始响应: {raw[:200]}")
    except Exception as e:
        print(f"    LLM 维度分类异常: {e}")

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
    project_name = data.get("projectName", "default")
    # projectRoot 优先级：请求参数 > API 设置 > 环境变量
    project_root = data.get("projectRoot") or _project_root_map.get(project_name) or PROJECT_ROOT
    persona_state = load_state(project_name)

    if not prompt:
        raise APIError("请输入问题", 400)

    sub_questions = split_user_question(prompt, context_files)
    if not sub_questions or len(sub_questions) <= 1:
        sub_questions = [{"id": "1", "prompt": prompt, "contextHint": ""}]

    def generate():
        prev_summary = None
        session = _get_session(project_name)

        for i, sq in enumerate(sub_questions):
            sub_prompt = sq["prompt"]
            if prev_summary and sq.get("dependsOn"):
                sub_prompt = f"上一步: {prev_summary}\n\n当前: {sub_prompt}"

            full_prompt = f"原始问题: {prompt}\n\n当前子任务: {sub_prompt}"

            # Session 上下文注入
            session_history = session.build_context(max_entries=4)
            session_context = ""
            if session_history:
                lines = [f"{m['role']}: {m['content'][:200]}" for m in session_history]
                session_context = "\n".join(lines)
                full_prompt = f"对话历史:\n{session_context}\n\n---\n\n{full_prompt}"

            # RAG 检索相关记忆
            memory_store = _get_memory(project_name)
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

            # 记录用户问题到 Session
            session.append("question", {"text": sub_prompt})

            # SSE: 子问题开始 + session/turn 事件
            yield create_segment_start(i, len(sub_questions), sq["id"], sq.get("contextHint", ""))

            result = generate_dual_answers(full_prompt, context_files, eye_data, persona_state, project_root)

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

            # 记录答案到 Session
            session.append("answer_a", {"text": answer_a}, parent_id=None)  # 挂在 question 下
            session.append("answer_b", {"text": answer_b}, parent_id=None)

            # SSE: 子问题结束
            yield create_segment_end(i, len(sub_questions), sq["id"], result.get("success", False))

            if result.get("success"):
                preview = answer_b[:200] + "..." if len(answer_b) > 200 else answer_b
                prev_summary = preview

        # 提取 semantic 记忆
        mem = _get_memory(project_name)
        if mem.count() < 50:
            try:
                best_answer = result.get("answerB", "") or result.get("answerA", "")
                if best_answer and len(best_answer) > 50:
                    added = extract_semantic_memories(mem, llm_client, prompt, best_answer)
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
    project_root = data.get("projectRoot") or _project_root_map.get(project_name) or PROJECT_ROOT
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

            result = generate_dual_answers(sq["prompt"], context_files, persona_state=persona_state, project_root=project_root)
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
    project_name = data.get("projectName", "default")
    current_question = data.get("currentQuestion", "")
    persona_state = load_state(project_name)

    # ==== 实验场景追踪字段（场景 A/B/C/D/E 控制）====
    scene_id = data.get("sceneId", "")          # 所属场景
    expected_dim = data.get("expectedDim", "")  # 预期匹配维度（场景E）
    control_side = data.get("controlSide", "")  # 控制策略: fixed_a / fixed_b / random

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
        "scene_id": scene_id,
        "expected_dim": expected_dim,
        "control_side": control_side,
        "projectName": project_name,
        "experimentMode": experiment_mode,
        "preference": preference,
        "eyeMetrics": eye_metrics,
        "answerALength": answer_a_length,
        "answerBLength": answer_b_length,
        "adjustments": eye_processor.get_prompt_adjustments(),
        "processedScores": processed_scores,
        "timestamp": datetime.now().isoformat(),
    }

    # 实验数据仅在内存中用于日志展示，不持久化
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

    # 从眼动数据计算置信度，传给 Persona 维度更新
    eye_confidence = None
    eye_bias = None
    if eye_result and eye_result.get("valid"):
        bias_val = eye_result.get("persona_bias", 0.5)
        strength = min(1.0, abs(bias_val - 0.5) * 4)
        maturity = min(1.0, eye_result.get("round_count", 1) / 3)
        eye_confidence = strength * maturity
        eye_bias = bias_val

    # 记录选择到 Session
    session = _get_session(project_name)
    final_choice = preference.get("finalChoice", None)
    if final_choice in ("A", "B"):
        session.append("choice", {
            "side": final_choice,
            "detail_score": adjustments.get("detail_score", 0.5),
            "explanation_score": adjustments.get("explanation_score", 0.5),
        })

    # 更新 Persona 状态
    if final_choice in ("A", "B") and persona_state:
        # 判断问题涉及哪些维度
        # 先用 LLM 分类，失败回退到关键词
        relevant_dims = None
        dim_reasonings = {}
        dim_classify_source = "全部未收敛"
        if current_question:
            # 先试 LLM 分类（带推理）
            llm_result = classify_dimensions_llm(current_question)
            if llm_result is not None:
                relevant_dims = llm_result["dims"]
                dim_reasonings = llm_result["reasonings"]
                dim_classify_source = "LLM"
                if relevant_dims:
                    print(f"    LLM 维度分类: {relevant_dims}")
                    for d, r in dim_reasonings.items():
                        print(f"      {d}: {r[:100]}{'...' if len(r) > 100 else ''}")
                else:
                    print(f"    LLM 分类结果为空（问题不涉及特定维度），跳过维度调整")
            else:
                print(f"    LLM 维度分类失败(返回None)，尝试关键词回退...")
                kw_result = classify_dimensions(current_question)
                relevant_dims = kw_result["dims"]
                dim_reasonings = kw_result["reasonings"]
                if relevant_dims:
                    dim_classify_source = "关键词"
                    print(f"    关键词维度分类: {relevant_dims}")
                    for d, r in dim_reasonings.items():
                        print(f"      {d}: {r}")
                else:
                    print(f"    关键词匹配无结果，全部未收敛维度参与调整")

        updated_state = record_choice(
            persona_state, final_choice, relevant_dims,
            eye_confidence=eye_confidence,
            eye_bias=eye_bias,
            dim_reasonings=dim_reasonings if dim_reasonings else None,
        )
        from persona_state import DIMS_LABEL, NEUTRAL_BIAS_THRESHOLD

        # 眼动调制摘要
        if eye_confidence is not None:
            bias_val = eye_bias or 0.5
            rc = adjustments.get("round_count", 0)
            if abs(bias_val - 0.5) > NEUTRAL_BIAS_THRESHOLD:
                eye_side = "A" if bias_val > 0.5 else "B"
                consistent = "一致" if eye_side == final_choice else "矛盾"
                mode = f"偏{eye_side}, {consistent}"
            else:
                mode = "中性"
            print(f"    眼动调制: conf={eye_confidence:.2f}, bias={bias_val:.2f}, round={rc} ({mode})")
        else:
            print("    眼动调制: 无眼动数据，使用基础调整速度")
        save_state(project_name, updated_state)
        log_state_change(updated_state, project_name)

        # 收敛状态摘要
        all_dims = updated_state.get("dimensions", {})
        converged_dims = [dim for dim, info in all_dims.items() if info.get("converged")]
        unconverged_dims = [dim for dim in all_dims if not all_dims[dim].get("converged")]
        total = len(all_dims)
        persona_gap = get_persona_bias(updated_state)

        if converged_dims:
            names = ", ".join(DIMS_LABEL.get(d, d) for d in converged_dims)
            print(f"    已收敛({len(converged_dims)}/{total}): {names}")
        if unconverged_dims:
            names = ", ".join(DIMS_LABEL.get(d, d) for d in unconverged_dims)
            print(f"    学习中({len(unconverged_dims)}/{total}): {names}")
        print(f"    Persona 偏差: {persona_gap:.4f} (分类来源: {dim_classify_source})")

        # 记录 Persona 变化到 Session
        converged_names = [DIMS_LABEL.get(d, d) for d in converged_dims]
        converged_summary = ", ".join(converged_names) if converged_names else "无新收敛"
        session.append("persona_change", {
            "summary": f"选{final_choice}, 收敛: {converged_summary}",
            "final_choice": final_choice,
            "converged_count": len(converged_dims),
        })
        all_done = updated_state.get('all_converged', False)
        if all_done:
            print("    所有维度已收敛，未选中侧进入随机探索模式")

        # 保存 episodic 记忆
        mem = _get_memory(project_name)
        try:
            mem.add_episodic(
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
    print(f"    成功: {summary.get('successful', 0)}")
    print(f"    总 Token: {summary['total_tokens']}")
    print(f"    平均延迟: {summary['avg_latency_ms']}ms")
    print("─" * 60 + "\n")

    return jsonify({"success": True})


@app.route("/api/eye-model", methods=["GET"])
def get_eye_model():
    """获取眼动模型状态 (用于调试)"""
    return jsonify(eye_processor.to_dict())


@app.route("/api/eye-model/reset", methods=["POST"])
def reset_eye_model():
    """重置眼动模型 + 项目数据"""
    global eye_processor
    data = request.get_json(silent=True) or {}
    project_name = data.get("projectName", "default")

    eye_storage.clear()
    eye_processor = EyeTrackerProcessor(storage=eye_storage, storage_key="default")
    reset_state(project_name)
    if project_name in _memory_stores:
        _memory_stores[project_name].clear()
    _get_session(project_name).clear()
    print(f"\n  眼动模型 + Persona + 记忆 + Session 已重置 (项目: {project_name})\n")
    return jsonify({"success": True})


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
        "projects": {
            "active": list(_memory_stores.keys()),
        },
    })


@app.route("/api/project-root", methods=["POST", "GET"])
def project_root_api():
    """设置/获取项目根目录（供前端 UI 使用）"""
    if request.method == "POST":
        data = request.json or {}
        project_name = data.get("projectName", "default")
        root_path = data.get("projectRoot", "")
        if root_path:
            import os
            root_path = os.path.expanduser(root_path)
            if os.path.isdir(root_path):
                _project_root_map[project_name] = root_path
                print(f"  [项目] 设置 projectRoot[{project_name}] = {root_path}")
                return jsonify({"success": True, "projectRoot": root_path})
            else:
                return jsonify({"success": False, "error": f"目录不存在: {root_path}"}), 400
        else:
            _project_root_map.pop(project_name, None)
            return jsonify({"success": True, "projectRoot": None})

    # GET
    project_name = request.args.get("projectName", "default")
    root = _project_root_map.get(project_name) or PROJECT_ROOT or None
    return jsonify({"projectRoot": root, "source": "api" if project_name in _project_root_map else "env" if PROJECT_ROOT else None})


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
    print(f"  LLMClient: {LLM_MODEL} (retry={LLM_MAX_RETRIES}, timeout={LLM_TIMEOUT}s)")
    print("  PromptBuilder: 动态组装 + 眼动调整")
    print(f"  EyeTracker: EMA α = {ALPHA}")
    print(f"  LLMLogger: {llm_logger.log_dir / '*.jsonl'}")
    print("  访问 http://localhost:8000/api/health 检查状态")
    print("  访问 http://localhost:8000/api/stats 查看统计")
    print("=" * 60)
    app.run(host="0.0.0.0", port=8000, debug=True, use_reloader=False)
