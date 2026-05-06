"""GazeVibe 后端配置常量"""

# 眼动数据处理 (eye_tracker_processor.py)
ALPHA = 0.3  # EMA 平滑系数
INITIAL_DETAIL = 0.5  # 详细程度初始值
INITIAL_EXPLANATION = 0.5  # 解释程度初始值
MIN_EYE_TIME = 2000  # 最小眼动时长阈值 (ms)
