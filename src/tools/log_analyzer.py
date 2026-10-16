"""智能日志分析工具。

分析链路：
1. 从日志中抽取 ERROR/FATAL/WARN 片段与统计信息；
2. 优先调用本地 Ollama 大模型做语义级根因分析（数据不出本机）；
3. Ollama 不可用时，自动降级为内置规则引擎，保证始终有结果。
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Optional

from src.config import CONFIG
from src.llm.ollama_client import OllamaClient, heuristic_analyze
from src.tools.log_reader import (
    _open_log, _validate_file, detect_level, get_log_stats,
)

_client = OllamaClient()

_SYSTEM_PROMPT = (
    "你是一名资深 SRE 与后端排障专家。用户会给你应用日志片段。"
    "请严格基于日志中的证据分析，禁止编造日志里不存在的信息。"
    "使用中文输出 Markdown，结构如下：\n"
    "## 一、结论概要\n用 1-2 句话说明最可能的根因。\n"
    "## 二、关键证据\n引用日志中的具体报错行（最多 3 条）。\n"
    "## 三、可能根因\n按可能性从高到低列出，标注置信度（高/中/低）。\n"
    "## 四、修复建议\n给出可执行的排查与修复步骤，命令用反引号标注。\n"
    "## 五、预防措施\n避免问题复发的工程化建议。"
)


def _collect_errors(file_path: str, max_lines: int) -> tuple[str, dict]:
    """读取日志并抽取错误片段与统计信息。"""
    p = _validate_file(file_path)
    if p is None:
        raise FileNotFoundError(file_path)

    level_counts: Counter[str] = Counter()
    errors: list[str] = []
    tail: list[str] = []
    total = 0
    max_keep = max(50, min(int(max_lines), int(CONFIG["max_log_lines"])))

    with _open_log(p) as f:
        for line in f:
            total += 1
            tail.append(line.rstrip())
            if len(tail) > max_keep:
                tail.pop(0)
            lv = detect_level(line)
            if lv:
                level_counts[lv] += 1
            if lv in ("ERROR", "FATAL"):
                errors.append(line.rstrip())

    # 优先错误片段；错误不足时补充末尾日志作为上下文
    parts: list[str] = []
    if errors:
        parts.append("【错误日志】")
        parts.extend(errors[:max_keep])
    if len(errors) < 10:
        parts.append("\n【日志末尾上下文】")
        parts.extend(tail[-100:])

    stats = {"total_lines": total, "level_counts": dict(level_counts)}
    return "\n".join(parts), stats


def check_llm_status() -> str:
    """检查本地大模型（Ollama）连接与模型可用状态。"""
    ok, msg = _client.health_check()
    icon = "✅" if ok else "⚠️"
    suffix = "" if ok else "\n当前分析类工具将自动使用内置规则引擎，功能不受影响。"
    return f"{icon} {msg}{suffix}"


def analyze_log(file_path: str, max_lines: int = 0) -> str:
    """智能分析整个日志文件：抽取错误并给出根因与修复建议。"""
    p = _validate_file(file_path)
    if p is None:
        return f"[错误] 文件不存在：{file_path}"
    if max_lines <= 0:
        max_lines = int(CONFIG["max_log_lines"])

    try:
        error_text, stats = _collect_errors(file_path, max_lines)
    except OSError as exc:
        return f"[错误] 读取日志失败：{exc}"

    if not error_text.strip():
        return f"日志文件 {file_path} 中未发现任何 ERROR/FATAL 级别记录，服务看起来运行正常。"

    ok, status = _client.health_check()
    stats_text = get_log_stats(file_path)
    if not ok:
        report = heuristic_analyze(error_text, stats)
        return (f"> {status}\n\n{stats_text}\n\n---\n\n{report}")

    prompt = (
        f"以下是日志统计信息：\n```\n{stats_text}\n```\n\n"
        f"以下是需要分析的日志片段：\n```\n{error_text[:12000]}\n```\n"
        "请按要求分析根因并给出修复建议。"
    )
    try:
        answer = _client.generate(prompt, system=_SYSTEM_PROMPT)
        header = f"# 日志智能分析报告（本地模型 {_client.model}）\n\n{stats_text}\n\n---\n\n"
        return header + answer
    except Exception as exc:  # noqa: BLE001 - 模型调用失败时降级，保证可用
        report = heuristic_analyze(error_text, stats)
        warn = f"> 本地模型调用失败（{exc}），已自动切换为内置规则引擎。\n\n"
        return warn + stats_text + "\n\n---\n\n" + report


def analyze_error_text(error_text: str) -> str:
    """直接对用户粘贴的一段错误/堆栈文本进行智能分析（无需日志文件）。"""
    if not error_text or not error_text.strip():
        return "[错误] 错误日志内容不能为空。"

    ok, status = _client.health_check()
    if not ok:
        return f"> {status}\n\n---\n\n" + heuristic_analyze(error_text)

    prompt = f"以下是需要分析的报错片段：\n```\n{error_text[:12000]}\n```\n请按要求分析。"
    try:
        answer = _client.generate(prompt, system=_SYSTEM_PROMPT)
        return f"# 报错智能分析（本地模型 {_client.model}）\n\n---\n\n" + answer
    except Exception as exc:  # noqa: BLE001
        return (f"> 本地模型调用失败（{exc}），已切换为内置规则引擎。\n\n---\n\n"
                + heuristic_analyze(error_text))
