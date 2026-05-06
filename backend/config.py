"""GazeVibe 后端配置常量

⚠️ 同步要求:
与 frontend/src/config.js 共享以下常量的数值:
- ALPHA (前端: ALPHA)
- MIN_EYE_TIME (前端: MIN_EYE_TIME)

修改任一侧后，必须同步更新另一侧。
"""

# ===== 眼动数据处理 (eye_tracker_processor.py) =====

# 与前端 config.js ALPHA 同步
ALPHA = 0.3  # EMA 平滑系数

INITIAL_DETAIL = 0.5  # 详细程度初始值
INITIAL_EXPLANATION = 0.5  # 解释程度初始值

# 与前端 config.js MIN_EYE_TIME 同步
MIN_EYE_TIME = 2000  # 最小眼动时长阈值 (ms)
