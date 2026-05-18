"""Tool 系统单元测试"""

import tempfile
from pathlib import Path

from tool import (
    Tool,
    default_tools,
    make_read_file_tool,
    make_write_file_tool,
    make_search_code_tool,
    make_list_files_tool,
    make_create_directory_tool,
    resolve_project_path,
)


def test_tool_to_openai_schema():
    """验证 Tool 能正确转为 OpenAI function calling schema"""
    tools = default_tools(".")
    schema = tools[0].to_openai_schema()
    assert schema["type"] == "function"
    assert "name" in schema["function"]
    assert "description" in schema["function"]
    assert "parameters" in schema["function"]


def test_tool_execute_read_file():
    """读取自身测试文件"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建测试文件
        test_file = Path(tmpdir) / "hello.txt"
        test_file.write_text("Hello, World!")
        tool = make_read_file_tool(tmpdir)
        result = tool.execute(file_path="hello.txt")
        assert "Hello, World!" in result


def test_tool_execute_write_file():
    """写入并验证"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tool = make_write_file_tool(tmpdir)
        result = tool.execute(file_path="src/main.py", content="print('hello')")
        assert "✓" in result

        # 验证文件真实存在
        created = Path(tmpdir) / "src" / "main.py"
        assert created.exists()
        assert created.read_text() == "print('hello')"


def test_tool_execute_write_overwrite():
    """覆盖已有文件"""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("old content")

        tool = make_write_file_tool(tmpdir)
        result = tool.execute(file_path="test.txt", content="new content")
        assert "更新" in result
        assert test_file.read_text() == "new content"


def test_tool_read_nonexistent_file():
    """读取不存在的文件应返回友好提示"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tool = make_read_file_tool(tmpdir)
        result = tool.execute(file_path="nonexistent.py")
        assert "不存在" in result


def test_tool_search_code():
    """搜索代码"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        (tmp / "src").mkdir()
        (tmp / "src" / "main.py").write_text("def hello():\n    print('hello world')")

        tool = make_search_code_tool(tmpdir)
        result = tool.execute(pattern="hello")
        assert "hello" in result
        assert "main.py" in result


def test_tool_list_files():
    """列出目录结构"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        (tmp / "src").mkdir()
        (tmp / "src" / "main.py").write_text("")
        (tmp / "README.md").write_text("")

        tool = make_list_files_tool(tmpdir)
        result = tool.execute(dir_path=".")
        assert "README.md" in result
        assert "main.py" in result


def test_tool_create_directory():
    """创建目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tool = make_create_directory_tool(tmpdir)
        result = tool.execute(dir_path="new-dir/sub")
        assert "✓" in result
        assert (Path(tmpdir) / "new-dir" / "sub").exists()


def test_resolve_project_path_normal():
    """正常路径解析"""
    p = resolve_project_path("/tmp/test", "src/main.py")
    assert str(p) == "/tmp/test/src/main.py"


def test_resolve_project_path_traversal():
    """路径穿越应被阻止"""
    try:
        resolve_project_path("/tmp/test", "../etc/passwd")
        assert False, "应该抛出 ValueError"
    except ValueError:
        pass


def test_default_tools_count():
    """默认工具集应包含 5 个工具"""
    tools = default_tools(".")
    assert len(tools) == 5
    names = [t.name for t in tools]
    assert "read_file" in names
    assert "write_file" in names
    assert "search_code" in names
    assert "list_files" in names
    assert "create_directory" in names


def test_tool_output_truncation():
    """工具输出超过最大字符数应截断"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建一个很大的文件
        big_content = "x" * 5000
        (Path(tmpdir) / "big.txt").write_text(big_content)

        tool = make_read_file_tool(tmpdir)
        result = tool.execute(file_path="big.txt")
        assert len(result) < 3500  # 被截断
        assert "截断" in result
