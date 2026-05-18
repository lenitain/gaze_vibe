"""Storage 抽象单元测试"""

from storage import MemoryStorage, Storage


def test_memory_storage_set_get():
    store: Storage[dict] = MemoryStorage[dict]()
    store.set("key1", {"value": 42})
    assert store.get("key1") == {"value": 42}
    assert store.get("nonexistent") is None


def test_memory_storage_delete():
    store: Storage[dict] = MemoryStorage[dict]()
    store.set("key1", {"v": 1})
    assert store.delete("key1") is True
    assert store.get("key1") is None
    assert store.delete("key1") is False


def test_memory_storage_list_keys():
    store: Storage[dict] = MemoryStorage[dict]()
    store.set("a", {})
    store.set("b", {})
    store.set("c", {})
    keys = store.list_keys()
    assert sorted(keys) == ["a", "b", "c"]


def test_memory_storage_get_or_create():
    store: Storage[dict] = MemoryStorage[dict]()

    # 不存在时用 factory 创建
    val = store.get_or_create("new", lambda: {"created": True})
    assert val == {"created": True}
    assert store.get("new") == {"created": True}

    # 已存在时返回已有值，不调用 factory
    val2 = store.get_or_create("new", lambda: {"should_not_be_called": True})
    assert val2 == {"created": True}


def test_memory_storage_clear():
    store = MemoryStorage[dict]()
    store.set("k1", {})
    store.set("k2", {})
    store.clear()
    assert store.list_keys() == []


def test_memory_storage_contains():
    store = MemoryStorage[dict]()
    store.set("k", {})
    assert "k" in store
    assert "x" not in store


def test_memory_storage_len():
    store = MemoryStorage[dict]()
    assert len(store) == 0
    store.set("k", {})
    assert len(store) == 1


def test_memory_storage_generic_with_int():
    """验证泛型支持不同类型的值"""
    store: Storage[list[int]] = MemoryStorage[list[int]]()
    store.set("scores", [1, 2, 3])
    assert store.get("scores") == [1, 2, 3]


def test_storage_is_abstract():
    """Storage 不能直接实例化"""
    import pytest
    with pytest.raises(TypeError):
        Storage()  # type: ignore
