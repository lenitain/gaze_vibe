"""
LLM 调用日志

记录每次 LLM 调用的完整信息，用于调试、成本追踪和性能分析。
"""

import os
import json
import csv
import io
from pathlib import Path
from datetime import datetime
from typing import Any
from dataclasses import dataclass, field, asdict


# ===== 日志记录 =====

@dataclass
class LogEntry:
    """单次 LLM 调用日志"""
    timestamp: str = ""
    model: str = ""
    system_prompt: str = ""
    user_prompt: str = ""
    response: str = ""
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    success: bool = True
    error: str = ""
    retry_count: int = 0
    caller: str = ""  # 调用来源标识（如 "generate_dual_answers"）
    metadata: dict = field(default_factory=dict)


class LLMLogger:
    """
    LLM 调用日志记录器

    支持：
    - JSONL 持久化
    - 会话级摘要统计
    - 回调接口（与 LLMClient.on_record 兼容）
    """

    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # 当前会话文件
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._log_file = self.log_dir / f"llm_calls_{session_id}.jsonl"

        # 会话统计
        self.session_entries: list[LogEntry] = []

    def record(self, entry: LogEntry):
        """记录一次调用"""
        self.session_entries.append(entry)
        self._append_jsonl(entry)
        self._print_summary(entry)

    def record_from_llm_record(self, record: Any, caller: str = "", metadata: dict | None = None):
        """从 LLMClient 的 LLMCallRecord 转换记录"""
        entry = LogEntry(
            timestamp=record.timestamp or datetime.now().isoformat(),
            model=record.model,
            system_prompt=record.system_prompt_preview,
            user_prompt=record.user_prompt_preview,
            response=record.response_preview,
            latency_ms=record.latency_ms,
            input_tokens=record.usage.input_tokens,
            output_tokens=record.usage.output_tokens,
            total_tokens=record.usage.total_tokens,
            success=record.success,
            error=record.error,
            retry_count=record.retry_count,
            caller=caller,
            metadata=metadata or {},
        )
        self.record(entry)

    def _append_jsonl(self, entry: LogEntry):
        """追加到 JSONL 文件"""
        try:
            with open(self._log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"  [Logger] 写入日志失败: {e}")

    def _print_summary(self, entry: LogEntry):
        """控制台输出简洁日志"""
        status = "✓" if entry.success else "✗"
        tokens = f"{entry.input_tokens}→{entry.output_tokens} tok"
        latency = f"{entry.latency_ms:.0f}ms"
        print(f"  [{status}] {entry.model} | {tokens} | {latency} | {entry.caller}")

    def session_summary(self) -> dict:
        """当前会话统计摘要"""
        entries = self.session_entries
        if not entries:
            return {"total_calls": 0}

        total_input = sum(e.input_tokens for e in entries if e.success)
        total_output = sum(e.output_tokens for e in entries if e.success)
        succeeded = [e for e in entries if e.success]
        avg_latency = sum(e.latency_ms for e in succeeded) / max(1, len(succeeded))

        return {
            "total_calls": len(entries),
            "successful": len(succeeded),
            "failed": len(entries) - len(succeeded),
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_tokens": total_input + total_output,
            "avg_latency_ms": round(avg_latency, 1),
            "log_file": str(self._log_file),
        }

    def export_csv(self, filepath: str | None = None) -> str:
        """导出为 CSV"""
        if not filepath:
            filepath = str(self.log_dir / f"llm_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "model", "latency_ms", "input_tokens", "output_tokens", "success", "caller"])
            for e in self.session_entries:
                writer.writerow([e.timestamp, e.model, e.latency_ms, e.input_tokens, e.output_tokens, e.success, e.caller])

        return filepath


# ===== 上下文窗口管理 =====

def estimate_tokens(text: str) -> int:
    """粗略估算 token 数（中文约 1.5 字符/token，英文约 4 字符/token）"""
    if not text:
        return 0
    chinese = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    english = len(text) - chinese
    return int(chinese * 1.5 + english / 4)


def truncate_context(
    messages: list[dict],
    max_tokens: int = 8000,
    reserve_output: int = 2000,
) -> list[dict]:
    """
    截断上下文以适配窗口

    策略：从最早的消息开始删除，保留最近的。
    始终保留 system prompt 和最后一条 user message。
    """
    if not messages:
        return messages

    available = max_tokens - reserve_output

    # 始终保留 system prompt
    system = [m for m in messages if m.get("role") == "system"]
    others = [m for m in messages if m.get("role") != "system"]

    # 从前往后删除，直到 token 数在范围内
    while others and estimate_tokens(str(others)) > available:
        # 保留最后一条
        if len(others) <= 1:
            break
        others.pop(0)

    return system + others


# ===== 便捷工厂 =====

def create_logger(log_dir: str = "logs") -> LLMLogger:
    """创建并返回 LLM 日志记录器"""
    return LLMLogger(log_dir=log_dir)
