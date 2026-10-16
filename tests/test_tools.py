"""工具函数单元测试（不依赖 MCP 与 Ollama）。

运行方式（在项目根目录）：
    python -m pytest tests/ -v
或直接：
    python tests/test_tools.py
"""
from __future__ import annotations

import gzip
import sys
import tempfile
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.llm.ollama_client import heuristic_analyze  # noqa: E402
from src.tools import log_analyzer, log_reader  # noqa: E402

SAMPLE = PROJECT_ROOT / "examples" / "sample.log"


def test_level_detection() -> None:
    assert log_reader.detect_level("2026-10-16 09:03:01 ERROR payment - fail") == "ERROR"
    assert log_reader.detect_level("[WARNING] something") == "WARN"
    assert log_reader.detect_level("FATAL crash here") == "FATAL"
    assert log_reader.detect_level("a normal line without level") is None


def test_stats() -> None:
    report = log_reader.get_log_stats(str(SAMPLE))
    assert "总行数" in report
    assert "ERROR" in report
    assert "高频错误" in report


def test_filter_error() -> None:
    report = log_reader.filter_log_by_level(str(SAMPLE), "ERROR")
    assert "Connection refused" in report
    assert "OutOfMemoryError" in report


def test_search() -> None:
    report = log_reader.search_log_keyword(str(SAMPLE), "timeout", regex=False)
    assert "timed out" in report.lower()


def test_tail_head() -> None:
    tail = log_reader.read_log_tail(str(SAMPLE), 3)
    assert "FATAL" in tail
    head = log_reader.read_log_head(str(SAMPLE), 2)
    assert "Starting" in head


def test_missing_file() -> None:
    assert "[错误]" in log_reader.get_log_stats("Z:/no/such/file.log")
    assert "[错误]" in log_reader.list_log_files("Z:/no/such/dir")


def test_heuristic() -> None:
    out = heuristic_analyze("java.net.ConnectException: Connection refused")
    assert "目标服务未启动" in out
    out2 = heuristic_analyze("java.lang.OutOfMemoryError: Java heap space")
    assert "内存溢出" in out2


def test_analyze_log_without_ollama() -> None:
    """Ollama 未安装时应自动降级为规则引擎，而非报错。"""
    out = log_analyzer.analyze_log(str(SAMPLE))
    assert "规则引擎" in out or "本地模型" in out
    assert "Connection refused" in out or "连接" in out


def test_gzip_log() -> None:
    """gzip 压缩日志应被透明读取、统计与分析。"""
    raw = SAMPLE.read_bytes()
    with tempfile.TemporaryDirectory() as tmp:
        gz_path = Path(tmp) / "app.log.gz"
        with gzip.open(gz_path, "wb") as gz:
            gz.write(raw)

        tail = log_reader.read_log_tail(str(gz_path), 3)
        assert "FATAL" in tail
        stats = log_reader.get_log_stats(str(gz_path))
        assert "ERROR=10" in stats and "压缩包" in stats
        hit = log_reader.search_log_keyword(str(gz_path), "Connection refused")
        assert "Connection refused" in hit
        out = log_analyzer.analyze_log(str(gz_path))
        assert "连接" in out or "Connection refused" in out


def test_zip_log() -> None:
    """zip 压缩包（含多个成员）应被合并读取与统计。"""
    raw = SAMPLE.read_bytes()
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / "bundle.log.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("app-1.log", raw)
            zf.writestr("app-2.log", b"2026-10-16 10:00:00 ERROR another.service - disk full\n")

        head = log_reader.read_log_head(str(zip_path), 5)
        assert "zip 成员" in head and "app-1.log" in head
        stats = log_reader.get_log_stats(str(zip_path))
        # 两个成员各含 10 条与 1 条 ERROR
        assert "ERROR=11" in stats
        out = log_analyzer.analyze_log(str(zip_path))
        assert "磁盘" in out or "Connection refused" in out


def _run_all() -> None:
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for fn in fns:
        fn()
        print(f"  PASS {fn.__name__}")
        passed += 1
    print(f"\n✅ {passed} 个测试全部通过")


if __name__ == "__main__":
    _run_all()
