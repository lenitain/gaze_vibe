"""
眼动处理器单元测试

测试 EyeTrackerProcessor 的核心功能：
- 数据有效性验证
- 分数计算
- EMA 长期建模
- 单维度 persona_bias 合并
- 序列化/反序列化
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from eye_tracker_processor import EyeTrackerProcessor


def make_eye_data(**overrides):
    """生成测试用眼动数据"""
    data = {
        "timeOnA": 5000,
        "timeOnB": 3000,
        "answerALength": 500,
        "answerBLength": 300,
        "saccadeCount": 10,
        "regressionRate": 0.1,
        "firstFixationRegion": "A",
        "firstFixationDuration": 1200,
        "fixationDurationVariance": 200000,
        "finalAttentionFocus": {"A": 2000, "B": 1000},
        "gazeBias": 0.6,
        "directionRatio": 0.5,
        "leftToRight": 5,
        "rightToLeft": 3,
        "lastFixationRegion": "A",
        "meanSwitchInterval": 800,
        "switchIntervalDecay": 0.1,
        "explorationRatio": 0.3,
        "tau": 0.5,
        "entropyChangeRate": 0.01,
        "decisionLatency": 500,
        "totalDurationA": 5000,
        "totalDurationB": 3000,
    }
    data.update(overrides)
    return data


def test_initial_values():
    """初始值为 0.5"""
    p = EyeTrackerProcessor()
    assert p.long_term_detail == 0.5
    assert p.long_term_explanation == 0.5
    assert p.long_term_persona_bias == 0.5
    assert p.round_count == 0


def test_invalid_data_returns_valid_false():
    """总时长不足 2000ms 时返回 valid=False"""
    p = EyeTrackerProcessor()
    data = make_eye_data(timeOnA=500, timeOnB=300)
    r = p.process(data)
    assert r["valid"] is False
    assert p.round_count == 1  # 即使无效也计数


def test_valid_data_returns_valid_true():
    """总时长 >= 2000ms 时返回 valid=True"""
    p = EyeTrackerProcessor()
    data = make_eye_data(timeOnA=4000, timeOnB=2000)
    r = p.process(data)
    assert r["valid"] is True


def test_detail_score_in_range():
    """detail_score 在 0~1 范围内"""
    p = EyeTrackerProcessor()
    data = make_eye_data(timeOnA=8000, timeOnB=1000, gazeBias=0.8)
    r = p.process(data)
    assert 0 <= r["detail_score"] <= 1


def test_explanation_score_in_range():
    """explanation_score 在 0~1 范围内"""
    p = EyeTrackerProcessor()
    r = p.process(make_eye_data())
    assert 0 <= r["explanation_score"] <= 1


def test_persona_bias_present():
    """返回数据包含 persona_bias"""
    p = EyeTrackerProcessor()
    r = p.process(make_eye_data())
    assert "persona_bias" in r
    assert 0 <= r["persona_bias"] <= 1


def test_persona_bias_is_average():
    """persona_bias = (detail + explanation) / 2"""
    p = EyeTrackerProcessor()
    r = p.process(make_eye_data())
    expected = (r["detail_score"] + r["explanation_score"]) / 2
    assert abs(r["persona_bias"] - expected) < 0.01


def test_ema_updates_long_term():
    """多次处理后长期模型发生变化"""
    p = EyeTrackerProcessor()
    initial_d = p.long_term_detail
    initial_e = p.long_term_explanation
    initial_p = p.long_term_persona_bias

    p.process(make_eye_data(timeOnA=8000, timeOnB=1000))
    p.process(make_eye_data(timeOnA=7000, timeOnB=2000))

    # 长期模型应该发生变化（偏向 A）
    assert p.long_term_detail != initial_d
    assert p.long_term_explanation != initial_e
    assert p.long_term_persona_bias != initial_p


def test_convergent_bias():
    """多次偏向 A 时 persona_bias > 0.5"""
    p = EyeTrackerProcessor()
    data_a = make_eye_data(timeOnA=9000, timeOnB=500, gazeBias=0.9)

    for _ in range(5):
        p.process(data_a)

    assert p.long_term_persona_bias > 0.5


def test_serialization():
    """to_dict / from_dict 往返一致"""
    p = EyeTrackerProcessor()
    p.process(make_eye_data())
    p.process(make_eye_data(timeOnA=3000, timeOnB=6000))

    d = p.to_dict()
    restored = EyeTrackerProcessor.from_dict(d)

    assert restored.long_term_detail == p.long_term_detail
    assert restored.long_term_explanation == p.long_term_explanation
    assert restored.long_term_persona_bias == p.long_term_persona_bias
    assert restored.round_count == p.round_count
    assert len(restored.history) == len(p.history)


def test_get_prompt_adjustments():
    """get_prompt_adjustments 包含 persona_bias"""
    p = EyeTrackerProcessor()
    p.process(make_eye_data())
    adj = p.get_prompt_adjustments()

    assert "detail_score" in adj
    assert "explanation_score" in adj
    assert "persona_bias" in adj
    assert "round_count" in adj


def test_thoughts_present():
    """process 返回 thoughts 列表"""
    p = EyeTrackerProcessor()
    r = p.process(make_eye_data())
    assert "thoughts" in r
    assert len(r["thoughts"]) > 0


def test_invalid_keeps_long_term():
    """无效数据不改变长期模型"""
    p = EyeTrackerProcessor()
    initial_d = p.long_term_detail
    initial_p = p.long_term_persona_bias

    p.process(make_eye_data(timeOnA=100, timeOnB=100))  # 无效

    assert p.long_term_detail == initial_d
    assert p.long_term_persona_bias == initial_p


def test_round_count_increments():
    """每处理一次 round_count +1"""
    p = EyeTrackerProcessor()
    assert p.round_count == 0
    p.process(make_eye_data())
    assert p.round_count == 1
    p.process(make_eye_data())
    assert p.round_count == 2


if __name__ == "__main__":
    # 手动运行
    tests = [
        test_initial_values,
        test_invalid_data_returns_valid_false,
        test_valid_data_returns_valid_true,
        test_detail_score_in_range,
        test_explanation_score_in_range,
        test_persona_bias_present,
        test_persona_bias_is_average,
        test_ema_updates_long_term,
        test_convergent_bias,
        test_serialization,
        test_get_prompt_adjustments,
        test_thoughts_present,
        test_invalid_keeps_long_term,
        test_round_count_increments,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  ✓ {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  ✗ {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ {t.__name__}: {type(e).__name__}: {e}")
            failed += 1
    print(f"\n{passed}/{passed+failed} 通过")
    sys.exit(0 if failed == 0 else 1)
