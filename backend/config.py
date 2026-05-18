"""GazeVibe 后端配置常量

⚠️ 同步要求:
与 frontend/src/config.js 共享以下常量的数值:
- ALPHA (前端: ALPHA)
- MIN_EYE_TIME (前端: MIN_EYE_TIME)

修改任一侧后，必须同步更新另一侧。
"""

import os


# ===== 眼动数据处理 (eye_tracker_processor.py) =====

# 与前端 config.js ALPHA 同步
ALPHA = 0.3  # EMA 平滑系数

INITIAL_DETAIL = 0.5  # 详细程度初始值
INITIAL_EXPLANATION = 0.5  # 解释程度初始值
INITIAL_PERSONA_BIAS = 0.5  # Persona 偏好初始值 (0=现代派, 1=稳健派)

# 与前端 config.js MIN_EYE_TIME 同步
MIN_EYE_TIME = 2000  # 最小眼动时长阈值 (ms)

# ===== LLM 客户端 (llm_client.py / app.py) =====
LLM_MODEL = "deepseek-chat"
LLM_BASE_URL = "https://api.deepseek.com"
LLM_MAX_RETRIES = 2
LLM_TIMEOUT = 120  # 秒

# ===== Embedding (vector_utils.py) =====
# DeepSeek embedding 模型（若不可用则自动跳过，不影响核心功能）
EMBEDDING_MODEL = "deepseek-embedding"

# ===== 项目根目录（可选，用于 AgentLoop 文件工具）=====
# 浏览器 File System Access API 不暴露完整路径，
# 设置此值可使后端在已知项目中直接读写文件。
# 设为空字符串 "" 则仅生成文本答案。
PROJECT_ROOT = os.getenv("PROJECT_ROOT", "")

# ===== Agent Loop (agent_loop.py) =====
AGENT_MAX_TURNS = 6
AGENT_TEMPERATURE = 0.3
AGENT_MAX_TOKENS = 4000

# ===== 双答案生成 (app.py) =====
ANSWER_TEMPERATURE = 0.7
ANSWER_MAX_TOKENS = 3000

# ===== 问题拆分 (app.py) =====
SPLIT_TEMPERATURE = 0.3
SPLIT_MAX_TOKENS = 2000
SPLIT_MAX_SUB_QUESTIONS = 4

# ===== 日志 =====
LOG_DIR = "logs"

# ===== RAG 记忆系统 =====
MEMORY_TOP_K = 5  # 检索返回的记忆条数
