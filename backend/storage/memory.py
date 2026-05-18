"""
MemoryStorage — 纯内存存储实现

功能等价于当前 _in_memory_states / MemoryStore 的内存模式。
进程退出即清空，无持久化。
"""

from __future__ import annotations

from typing import Generic, TypeVar

from storage.types import Storage

T = TypeVar("T")


class MemoryStorage(Storage[T], Generic[T]):
    """
    纯内存存储

    用 dict 包装，进程退出即清空。
    适用于开发/单进程场景。

    Example:
        >>> store = MemoryStorage[dict]()
        >>> store.set("default", {"version": 3})
        >>> store.get("default")
        {'version': 3}
    """

    def __init__(self):
        self._data: dict[str, T] = {}

    def get(self, key: str) -> T | None:
        return self._data.get(key)

    def set(self, key: str, value: T):
        self._data[key] = value

    def delete(self, key: str) -> bool:
        if key in self._data:
            del self._data[key]
            return True
        return False

    def list_keys(self) -> list[str]:
        return list(self._data.keys())

    def clear(self):
        """清空所有数据"""
        self._data.clear()

    def __len__(self) -> int:
        return len(self._data)

    def __contains__(self, key: str) -> bool:
        return key in self._data
