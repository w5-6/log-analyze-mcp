"""日志读取与分析的基础工具函数（不依赖 MCP，可独立测试）。

所有函数：
- 仅做本地只读操作，不修改任何日志文件；
- 采用流式逐行读取，避免大文件撑爆内存；
- 统一返回字符串，方便直接作为 MCP 工具结果交给 AI Agent。
"""
from __future__ import annotations

import gzip
import io
import os
import re
import zipfile
from collections import Counter, deque
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from src.config import CONFIG

# 日志级别归一化映射
_LEVEL_ALIAS = {
    "FATAL": "FATAL", "CRITICAL": "FATAL", "EMERGENCY": "FATAL", "SEVERE": "FATAL",
    "ERROR": "ERROR", "ERR": "ERROR",
    "WARN": "WARN", "WARNING": "WARN",
    "INFO": "INFO", "NOTICE": "INFO",
    "DEBUG": "DEBUG",
    "TRACE": "TRACE", "FINE": "TRACE", "FINER": "TRACE", "FINEST": "TRACE",
}
_LEVEL_ORDER = ["FATAL", "ERROR", "WARN", "INFO", "DEBUG", "TRACE"]

# 仅在行首 60 字符内寻找级别标记，降低误把正文单词当级别的概率
_LEVEL_RE = re.compile(
    r"\b(FATAL|CRITICAL|EMERGENCY|SEVERE|ERROR|ERR|WARNING|WARN|INFO|NOTICE|"
    r"DEBUG|TRACE|FINEST|FINER|FINE)\b",
    re.IGNORECASE,
)
_TS_RE = re.compile(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?")


def _validate_file(file_path: str) -> Optional[Path]:
    """校验文件路径，返回 Path；非法时返回 None。"""
    p = Path(file_path).expanduser()
    if not p.exists():
        return None
    if not p.is_file():
        return None
    return p


def _zip_lines(path: Path) -> Iterator[str]:
    """依次读取 zip 压缩包内全部文本成员，成员起始处插入分隔行。"""
    with zipfile.ZipFile(path) as zf:
        members = [n for n in zf.namelist() if not n.endswith("/")]
        for name in sorted(members):
            yield f"########## [zip 成员] {name} ##########\n"
            with zf.open(name) as raw:
                wrapper = io.TextIOWrapper(raw, encoding="utf-8", errors="ignore")
                try:
                    for line in wrapper:
                        yield line
                finally:
                    wrapper.detach()  # 避免关闭由 ZipFile 管理的底层流


@contextmanager
def _open_log(path: Path) -> Iterator[Iterator[str]]:
    """打开日志并返回「逐行文本迭代器」，透明支持压缩格式。

    - 普通文本（.log/.txt/.out/...）：直接打开；
    - gzip（.gz，如 app.log.gz）：gzip 流式解压；
    - zip（.zip）：依次读取压缩包内全部文本成员，成员起始处插入分隔行。
    所有格式均以 utf-8 容错解码，跳过无法识别的字节；调用方必须在 with 块内
    消费完迭代器（zip 依赖底层 ZipFile 仍处于打开状态）。
    """
    suffix = path.suffix.lower()

    if suffix == ".gz":
        fh = gzip.open(path, "rt", encoding="utf-8", errors="ignore")
        try:
            yield fh
        finally:
            fh.close()
        return

    if suffix == ".zip":
        gen = _zip_lines(path)
        try:
            yield gen
        finally:
            gen.close()  # 确保未读完时也能及时关闭底层 ZipFile
        return

    fh = open(path, "r", encoding="utf-8", errors="ignore")
    try:
        yield fh
    finally:
        fh.close()


def detect_level(line: str) -> Optional[str]:
    """识别单行日志的级别，返回归一化级别（FATAL/ERROR/...），无法识别返回 None。"""
    head = line[:60]
    m = _LEVEL_RE.search(head)
    if m:
        return _LEVEL_ALIAS.get(m.group(1).upper())
    return None


def list_log_files(dir_path: str, recursive: bool = True) -> str:
    """列出目录下的日志文件（按修改时间倒序）。"""
    p = Path(dir_path).expanduser()
    if not p.exists():
        return f"[错误] 目录不存在：{dir_path}"
    if not p.is_dir():
        return f"[错误] 不是目录：{dir_path}"

    exts = {e.lower() for e in CONFIG["log_extensions"]}
    walker = p.rglob("*") if recursive else p.glob("*")
    files = [f for f in walker if f.is_file() and f.suffix.lower() in exts]
    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

    if not files:
        return f"目录 {dir_path} 下未找到日志文件（支持扩展名：{', '.join(sorted(exts))}）"

    lines = [f"在 {dir_path} 找到 {len(files)} 个日志文件（按修改时间倒序）："]
    for f in files[:50]:
        size_kb = f.stat().st_size / 1024
        size_str = f"{size_kb / 1024:.1f}MB" if size_kb >= 1024 else f"{size_kb:.1f}KB"
        mtime = os.path.getmtime(f)
        import time
        t = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime))
        lines.append(f"- {f}  |  {size_str}  |  更新于 {t}")
    if len(files) > 50:
        lines.append(f"... 仅显示前 50 个，共 {len(files)} 个")
    return "\n".join(lines)


def read_log_tail(file_path: str, lines: int = 100) -> str:
    """读取日志文件末尾 N 行（内存占用恒定，适合超大日志）。"""
    p = _validate_file(file_path)
    if p is None:
        return f"[错误] 文件不存在：{file_path}"
    lines = max(1, min(int(lines), 5000))

    with _open_log(p) as f:
        tail = deque(f, maxlen=lines)
    content = "".join(tail).rstrip()
    if not content:
        return f"文件 {file_path} 为空。"
    return f"### {file_path} 末尾 {len(tail)} 行 ###\n{content}"


def read_log_head(file_path: str, lines: int = 100) -> str:
    """读取日志文件开头 N 行。"""
    p = _validate_file(file_path)
    if p is None:
        return f"[错误] 文件不存在：{file_path}"
    lines = max(1, min(int(lines), 5000))

    out: list[str] = []
    with _open_log(p) as f:
        for i, line in enumerate(f):
            if i >= lines:
                break
            out.append(line)
    content = "".join(out).rstrip()
    if not content:
        return f"文件 {file_path} 为空。"
    return f"### {file_path} 开头 {len(out)} 行 ###\n{content}"


def search_log_keyword(file_path: str, keyword: str, regex: bool = False,
                       context: int = 2, max_results: int = 50) -> str:
    """按关键词（或正则）搜索日志，返回匹配行及上下文。"""
    p = _validate_file(file_path)
    if p is None:
        return f"[错误] 文件不存在：{file_path}"
    if not keyword:
        return "[错误] 搜索关键词不能为空。"

    if regex:
        try:
            pattern = re.compile(keyword, re.IGNORECASE)
        except re.error as exc:
            return f"[错误] 正则表达式无效：{exc}"
    else:
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)

    context = max(0, min(int(context), 10))
    max_results = max(1, min(int(max_results), 200))

    with _open_log(p) as f:
        all_lines = list(f)

    hits = [i for i, line in enumerate(all_lines) if pattern.search(line)]
    if not hits:
        return f"未找到匹配 “{keyword}” 的记录。"

    # 合并相邻命中窗口
    shown_ranges: list[tuple[int, int]] = []
    count = 0
    for idx in hits:
        start, end = max(0, idx - context), min(len(all_lines) - 1, idx + context)
        if shown_ranges and start <= shown_ranges[-1][1] + 1:
            shown_ranges[-1] = (shown_ranges[-1][0], max(shown_ranges[-1][1], end))
        else:
            if count >= max_results:
                break
            shown_ranges.append((start, end))
            count += 1

    blocks = []
    for start, end in shown_ranges:
        seg = []
        for i in range(start, end + 1):
            mark = ">>" if pattern.search(all_lines[i]) else "  "
            seg.append(f"{mark} {i + 1:>7}: {all_lines[i].rstrip()}")
        blocks.append("\n".join(seg))

    header = (f"### 搜索 “{keyword}”：共 {len(hits)} 处命中，"
              f"展示前 {min(len(hits), max_results)} 处（含上下文 {context} 行）###")
    return header + "\n\n" + "\n\n    ...\n\n".join(blocks)


def filter_log_by_level(file_path: str, level: str = "ERROR") -> str:
    """按级别筛选日志并统计出现次数（默认筛 ERROR）。"""
    p = _validate_file(file_path)
    if p is None:
        return f"[错误] 文件不存在：{file_path}"
    target = _LEVEL_ALIAS.get(level.strip().upper())
    if target is None:
        return f"[错误] 不支持的级别：{level}（可选 FATAL/ERROR/WARN/INFO/DEBUG/TRACE）"

    # 严重度排序：筛选目标级别及更严重的级别（如选 ERROR 会同时包含 FATAL）
    severity = ["TRACE", "DEBUG", "INFO", "WARN", "ERROR", "FATAL"]
    threshold = severity.index(target)
    wanted = {lv for lv in severity[threshold:]}

    matched: list[str] = []
    max_keep = int(CONFIG["max_log_lines"])
    with _open_log(p) as f:
        for line in f:
            lv = detect_level(line)
            if lv in wanted:
                matched.append(line.rstrip())

    if not matched:
        return f"未找到 {target} 及以上级别的日志。"

    shown = matched[:max_keep]
    head = f"### {file_path} 中 {target} 及以上级别日志共 {len(matched)} 条"
    if len(matched) > max_keep:
        head += f"（仅展示前 {max_keep} 条）"
    return head + " ###\n" + "\n".join(shown)


def _normalize_msg(line: str) -> str:
    """归一化日志行，用于错误去重：去时间戳、去数字、压缩空白。"""
    s = _TS_RE.sub("<TS>", line)
    s = re.sub(r"\d+", "#", s)
    s = re.sub(r"0x[0-9a-fA-F]+", "0x<HEX>", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:160]


def get_log_stats(file_path: str) -> str:
    """统计日志：总行数、级别分布、时间范围、高频错误 Top5。"""
    p = _validate_file(file_path)
    if p is None:
        return f"[错误] 文件不存在：{file_path}"

    level_counts: Counter[str] = Counter()
    total = 0
    first_ts: Optional[str] = None
    last_ts: Optional[str] = None
    error_msgs: Counter[str] = Counter()

    with _open_log(p) as f:
        for line in f:
            total += 1
            lv = detect_level(line)
            if lv:
                level_counts[lv] += 1
                if lv in ("ERROR", "FATAL"):
                    error_msgs[_normalize_msg(line)] += 1
            if first_ts is None:
                m = _TS_RE.search(line)
                if m:
                    first_ts = m.group(0)
            m = _TS_RE.search(line)
            if m:
                last_ts = m.group(0)

    size_mb = p.stat().st_size / 1024 / 1024
    compressed = p.suffix.lower() in (".gz", ".zip")
    size_note = "（压缩包，显示压缩后大小）" if compressed else ""
    out = [f"### 日志统计报告：{file_path} ###",
           f"- 文件大小：{size_mb:.2f} MB{size_note}",
           f"- 总行数：{total}"]
    if first_ts or last_ts:
        out.append(f"- 时间范围：{first_ts or '未知'}  →  {last_ts or '未知'}")
    if level_counts:
        dist = "，".join(f"{lv}={level_counts[lv]}" for lv in _LEVEL_ORDER if level_counts[lv])
        out.append(f"- 级别分布：{dist}")
    else:
        out.append("- 级别分布：未识别到标准级别标记")
    if error_msgs:
        out.append("- 高频错误 Top5：")
        for msg, cnt in error_msgs.most_common(5):
            out.append(f"    {cnt:>5} 次 | {msg}")
    return "\n".join(out)
