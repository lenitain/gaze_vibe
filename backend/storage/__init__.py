"""
GazeVibe Storage 抽象层

提供统一的数据存储接口，支持内存和可选的持久化后端。
"""

from storage.memory import MemoryStorage as MemoryStorage
from storage.types import Storage as Storage

__all__ = ["Storage", "MemoryStorage"]
