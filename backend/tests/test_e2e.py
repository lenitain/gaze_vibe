"""
端到端集成测试

模拟完整对话流程：
  提问 → 生成双答案 → 眼动处理 → 用户选择 → Persona更新 → Session记录

无需 LLM API，使用 MemoryStorage 隔离副作用。
"""

from eye_tracker_processor import EyeTrackerProcessor
from persona_state import load_state, save_state, record_choice, get_persona_bias, get_prompt_scores
from session import Session, SessionState
from storage import MemoryStorage
from result import Ok, ok, is_ok


def _make_eye_data(time_on_a: int = 5000, time_on_b: int = 2000) -> dict:
    """生成模拟眼动数据"""
    return {
        "timeOnA": time_on_a,
        "timeOnB": time_on_b,
        "leftToRight": 2,
        "rightToLeft": 1,
        "answerALength": 300,
        "answerBLength": 150,
        "gazeBias": time_on_a / (time_on_a + time_on_b) if (time_on_a + time_on_b) > 0 else 0.5,
        "regressionRate": 0.3,
        "saccadeCount": 3,
        "directionRatio": 0.5,
        "firstFixationRegion": "A",
        "firstFixationDuration": 2000,
        "lastFixationRegion": "A",
        "fixationDurationVariance": 800000,
        "meanSwitchInterval": 3000,
        "switchIntervalDecay": 1.0,
        "explorationRatio": 0.5,
        "finalAttentionFocus": {"A": 3000, "B": 1000},
        "tau": 0.1,
        "entropyChangeRate": 0.1,
        "decisionLatency": 7000,
        "totalDurationA": time_on_a,
        "totalDurationB": time_on_b,
    }


def test_e2e_full_conversation():
    """
    模拟完整对话流程：
    1. 加载 Persona 初始状态
    2. 处理眼动数据
    3. 用户选择
    4. 记录到 Session
    5. 验证状态变更
    """
    project = "e2e-test"
    eye_storage: MemoryStorage[dict] = MemoryStorage[dict]()
    session_storage: MemoryStorage[SessionState] = MemoryStorage[SessionState]()

    # === Round 1: 提问 → 眼动 → 选择 A ===
    ep = EyeTrackerProcessor(storage=eye_storage, storage_key=project)
    state = load_state(project)

    # 眼动数据处理
    eye_result = ep.process(_make_eye_data(time_on_a=6000, time_on_b=1000))
    assert eye_result["valid"] is True
    assert eye_result["detail_score"] > 0.5  # 更多时间看 A → 更详细

    # 用户选择 A
    updated = record_choice(state, "A", relevant_dims=["ecosystem_maturity"])
    save_state(project, updated)

    # 验证：选中侧(A)不变，未选中侧(B)向 A 收敛
    a_scores = updated["persona_a"]["scores"]
    b_scores = updated["persona_b"]["scores"]
    assert a_scores["ecosystem_maturity"] >= b_scores["ecosystem_maturity"]

    # Session 记录
    session = Session(session_storage, project)
    session.append("question", {"text": "What Rust crate for web?"})
    session.append("eye_data", eye_result)
    session.append("choice", {"side": "A"})
    session.append("persona_change", {"summary": "adjusted ecosystem_maturity"})

    assert session.entry_count == 4
    branch = session.get_branch()
    assert len(branch) == 4

    # === Round 2: 再次选择 B（反转信号）===
    eye_result2 = ep.process(_make_eye_data(time_on_a=1000, time_on_b=6000))
    assert eye_result2["valid"] is True

    state2 = load_state(project)
    updated2 = record_choice(state2, "B", relevant_dims=["ecosystem_maturity"])
    save_state(project, updated2)

    session.append("question", {"text": "Actually, I prefer simple solutions"})
    session.append("choice", {"side": "B"})

    # 验证 A/B 分差存在（还没收敛）
    bias = get_persona_bias(updated2)
    assert bias > 0

    # Session context
    ctx = session.build_context(max_entries=3)
    assert len(ctx) <= 3
    for c in ctx:
        assert "role" in c
        assert "content" in c

    # Session 持久化验证
    session2 = Session(session_storage, project)
    assert session2.entry_count == 6


def test_e2e_eye_processor_persistence():
    """验证眼动处理器通过 storage 持久化状态"""
    storage: MemoryStorage[dict] = MemoryStorage[dict]()

    ep1 = EyeTrackerProcessor(storage=storage, storage_key="eye-persist")
    ep1.process(_make_eye_data())
    assert ep1.round_count == 1

    ep2 = EyeTrackerProcessor(storage=storage, storage_key="eye-persist")
    assert ep2.round_count == 1
    assert ep2.long_term_detail == ep1.long_term_detail


def test_e2e_persona_convergence():
    """验证维度收敛逻辑"""
    project = "converge-test"
    state = load_state(project)

    # 连续选择 A（naming_style alpha=0.20 较慢，需要 ~8 轮）
    for i in range(10):
        state = record_choice(state, "A", relevant_dims=["naming_style"])
        save_state(project, state)

    # 验证 naming_style 维度收敛
    dims = state.get("dimensions", {})
    naming = dims.get("naming_style", {})
    assert naming.get("converged", False) is True, f"naming_style should converge after 10 A-choices"

    # A/B 分应该接近
    a = state["persona_a"]["scores"]["naming_style"]
    b = state["persona_b"]["scores"]["naming_style"]
    assert abs(a - b) < 0.6, f"A/B scores should be close after convergence: {a} vs {b}"


def test_e2e_persona_reversal():
    """验证反转信号解除收敛"""
    project = "reversal-test"
    state = load_state(project)

    # 先收敛（testing_strategy alpha=0.30，~6 轮可收敛）
    for i in range(8):
        state = record_choice(state, "A", relevant_dims=["testing_strategy"])
    save_state(project, state)
    assert state["dimensions"]["testing_strategy"]["converged"] is True

    # 连续选择 B（反转）
    for i in range(4):  # UNCONVERGE_THRESHOLD = 3
        state = record_choice(state, "B", relevant_dims=["testing_strategy"])
    save_state(project, state)

    # 验证解除收敛
    dim_info = state["dimensions"]["testing_strategy"]
    assert dim_info.get("converged", True) is False, "Should unconverge after repeated opposite choices"


def test_e2e_get_prompt_scores():
    """验证 get_prompt_scores 返回正确的侧分数"""
    project = "prompt-scores"
    state = load_state(project)

    scores_a = get_prompt_scores(state, "A")
    scores_b = get_prompt_scores(state, "B")

    assert scores_a["name"] == "稳健派"
    assert scores_b["name"] == "现代派"
    for dim in state.get("dimensions", {}):
        assert dim in scores_a["scores"]
        assert dim in scores_b["scores"]


def test_e2e_session_context_skip_eye():
    """验证 build_context 跳过眼动数据"""
    project = "ctx-skip"
    session_storage: MemoryStorage[SessionState] = MemoryStorage[SessionState]()
    session = Session(session_storage, project)

    session.append("question", {"text": "Q1"})
    session.append("eye_data", {"gazeBias": 0.8})
    session.append("answer_b", {"text": "A1"})

    ctx = session.build_context()
    assert len(ctx) == 2  # eye_data 被跳过
    assert ctx[0]["role"] == "user"
    assert ctx[1]["role"] == "assistant"
