"""
Storage 抽象接口

参考 pi 的 SessionStorage<T> 模式，提供统一的存储抽象。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar("T")
"""存储的元数据类型（如 PersonaState dict、EyeTracker 状态等）"""


class Storage(ABC, Generic[T]):
    """
    存储抽象基类

    提供 get/set 语义，不关心底层实现（内存/文件/数据库）。
    T 为元数据类型，由具体实现决定。
    """

    @abstractmethod
    def get(self, key: str) -> T | None:
        """获取指定 key 的元数据，不存在返回 None"""
        ...

    @abstractmethod
    def set(self, key: str, value: T):
        """设置/更新指定 key 的元数据"""
        ...

    @abstractmethod
    def delete(self, key: str) -> bool:
        """删除指定 key，返回是否成功删除"""
        ...

    @abstractmethod
    def list_keys(self) -> list[str]:
        """列出所有 key"""
        ...

    def get_or_create(self, key: str, factory):
        """获取 key，若不存在则用 factory() 创建并保存"""
        val = self.get(key)
        if val is not None:
            return val
        val = factory()
        self.set(key, val)
        return val
