"""Session 树单元测试"""

from session import Session, SessionEntry, SessionState
from storage import MemoryStorage


def _make_session() -> Session:
    storage: MemoryStorage[SessionState] = MemoryStorage[SessionState]()
    return Session(storage, "test-project")


def test_session_initial_state():
    s = _make_session()
    assert s.session_id != ""
    assert s.entry_count == 0
    assert len(s.get_branch()) == 0


def test_session_append_entry():
    s = _make_session()
    qid = s.append("question", {"text": "How do I write Rust?"})
    assert s.entry_count == 1
    assert qid != ""


def test_session_branch_linear():
    s = _make_session()
    s.append("question", {"text": "Q1"})
    s.append("answer_a", {"text": "A1"})
    s.append("answer_b", {"text": "B1"})
    s.append("choice", {"side": "A"})

    branch = s.get_branch()
    assert len(branch) == 4
    assert branch[0].type == "question"
    assert branch[1].type == "answer_a"
    assert branch[2].type == "answer_b"
    assert branch[3].type == "choice"


def test_session_build_context():
    s = _make_session()
    s.append("question", {"text": "Q1"})
    s.append("answer_a", {"text": "Detailed answer"})
    s.append("answer_b", {"text": "Concise answer"})

    ctx = s.build_context()
    assert len(ctx) == 3  # question + answer_a + answer_b
    assert ctx[0]["role"] == "user"
    assert ctx[0]["content"] == "Q1"
    assert ctx[1]["role"] == "assistant"
    assert "详细解答" in ctx[1]["content"]
    assert ctx[2]["role"] == "assistant"
    assert "简洁解答" in ctx[2]["content"]


def test_session_build_context_max_entries():
    s = _make_session()
    for i in range(10):
        s.append("question", {"text": f"Q{i}"})
        s.append("answer_b", {"text": f"A{i}"})

    ctx = s.build_context(max_entries=4)
    assert len(ctx) == 4


def test_session_persistence():
    storage: MemoryStorage[SessionState] = MemoryStorage[SessionState]()
    s1 = Session(storage, "persist-test")
    s1.append("question", {"text": "Q1"})
    s1.append("answer_a", {"text": "A1"})

    # 从同一 storage 重建
    s2 = Session(storage, "persist-test")
    assert s2.entry_count == 2
    branch = s2.get_branch()
    assert branch[0].data["text"] == "Q1"
    assert branch[1].data["text"] == "A1"


def test_session_clear():
    s = _make_session()
    s.append("question", {"text": "Q1"})
    s.clear()
    assert s.entry_count == 0
    assert s.get_branch() == []


def test_session_entry_auto_id():
    e = SessionEntry(type="question", data={"text": "test"})
    assert e.id != ""
    assert e.timestamp != ""


def test_session_entry_to_dict():
    e = SessionEntry(type="question", data={"text": "hello"})
    d = e.to_dict()
    assert d["type"] == "question"
    assert d["data"]["text"] == "hello"
    assert "id" in d
    assert "parentId" in d
    assert "timestamp" in d


def test_session_context_skips_eye_data():
    s = _make_session()
    s.append("question", {"text": "Q1"})
    s.append("eye_data", {"gazeBias": 0.7})
    s.append("answer_a", {"text": "A1"})

    ctx = s.build_context()
    assert len(ctx) == 2  # eye_data 被跳过
    assert ctx[0]["role"] == "user"
    assert ctx[1]["role"] == "assistant"


def test_session_context_persona_change():
    s = _make_session()
    s.append("question", {"text": "Q1"})
    s.append("persona_change", {"summary": "converged error_handling"})

    ctx = s.build_context()
    assert len(ctx) == 2
    assert ctx[1]["role"] == "system"
    assert "Persona" in ctx[1]["content"]
