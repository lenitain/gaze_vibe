"""
GazeVibe 统一 Result 类型

参考 pi 的 Result<T,E> 模式，提供显式错误处理而非 raise/try-except。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")
E = TypeVar("E")


@dataclass(frozen=True)
class Ok(Generic[T]):
    """成功结果"""
    value: T

    def __repr__(self) -> str:
        return f"Ok({self.value!r})"


@dataclass(frozen=True)
class Err(Generic[E]):
    """失败结果"""
    error: E

    def __repr__(self) -> str:
        return f"Err({self.error!r})"


# Result[T, E] = Ok[T] | Err[E]
# Python 3.14 支持 type 关键字（PEP 695）
type Result[T, E] = Ok[T] | Err[E]


# ===== 构造辅助 =====

def ok[T](value: T) -> Ok[T]:
    """构造 Ok 结果"""
    return Ok(value)


def err[E](error: E) -> Err[E]:
    """构造 Err 结果"""
    return Err(error)


def is_ok[T, E](r: Result[T, E]) -> bool:
    """检查是否为 Ok"""
    return isinstance(r, Ok)


def is_err[T, E](r: Result[T, E]) -> bool:
    """检查是否为 Err"""
    return isinstance(r, Err)


def unwrap[T, E](r: Result[T, E]) -> T:
    """从 Ok 中取出值；若是 Err 则抛出 ValueError"""
    if isinstance(r, Ok):
        return r.value
    raise ValueError(f"Called unwrap on Err: {r.error!r}")


def unwrap_or[T, E](r: Result[T, E], default: T) -> T:
    """从 Ok 中取出值；若是 Err 则返回默认值"""
    if isinstance(r, Ok):
        return r.value
    return default


def map_ok[T, E, U](r: Result[T, E], fn):
    """Ok 值映射；Err 透传"""
    if isinstance(r, Ok):
        return ok(fn(r.value))
    return r  # type: ignore


def map_err[T, E, F](r: Result[T, E], fn):
    """Err 映射；Ok 透传"""
    if isinstance(r, Err):
        return err(fn(r.error))
    return r  # type: ignore
