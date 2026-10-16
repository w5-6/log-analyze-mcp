"""LogAnalyze-MCP 服务入口。

基于官方 MCP SDK 的 FastMCP 实现，通过 stdio 与 Cursor / Claude Code /
Trae 等 AI Agent 通信。所有操作均在本地完成，日志不会上传云端。

直接运行：
    python src/server.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# 兼容「python src/server.py」直接启动：把项目根目录加入模块搜索路径
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# 兼容 mcp 1.x（FastMCP）与 mcp 2.x（重命名为 MCPServer）
try:
    from mcp.server.mcpserver import MCPServer as _MCPBase  # mcp >= 2.0
except ImportError:  # pragma: no cover - 取决于安装的 mcp 版本
    from mcp.server.fastmcp import FastMCP as _MCPBase  # mcp < 2.0

from src.tools import log_analyzer, log_reader  # noqa: E402

mcp = _MCPBase(
    "log-analyze-mcp",
    instructions=(
        "本地日志智能分析服务。可帮助用户列出、读取、搜索、筛选日志文件，"
        "统计级别分布与高频错误，并利用本地大模型（Ollama）分析错误根因、"
        "给出修复建议；未安装 Ollama 时自动使用内置规则引擎。"
        "排查问题的推荐顺序：list_log_files → get_log_stats → "
        "filter_log_by_level / search_log_keyword → analyze_log。"
    ),
)


# ---------------------------------------------------------------------------
# 工具注册：FastMCP 依据函数签名与 docstring 自动生成 MCP 工具描述
# ---------------------------------------------------------------------------

@mcp.tool()
def list_log_files(dir_path: str, recursive: bool = True) -> str:
    """列出指定目录下的所有日志文件（.log/.txt/.out/.err/.trace），含大小与修改时间。

    Args:
        dir_path: 日志目录的绝对路径。
        recursive: 是否递归扫描子目录，默认 True。
    """
    return log_reader.list_log_files(dir_path, recursive=recursive)


@mcp.tool()
def read_log_tail(file_path: str, lines: int = 100) -> str:
    """读取日志文件末尾指定行数（适合查看最新报错，对超大文件同样高效）。

    Args:
        file_path: 日志文件绝对路径。
        lines: 要读取的行数，默认 100，最大 5000。
    """
    return log_reader.read_log_tail(file_path, lines=lines)


@mcp.tool()
def read_log_head(file_path: str, lines: int = 100) -> str:
    """读取日志文件开头指定行数（适合查看启动参数与启动阶段日志）。

    Args:
        file_path: 日志文件绝对路径。
        lines: 要读取的行数，默认 100，最大 5000。
    """
    return log_reader.read_log_head(file_path, lines=lines)


@mcp.tool()
def search_log_keyword(file_path: str, keyword: str, regex: bool = False,
                       context: int = 2, max_results: int = 50) -> str:
    """在日志中按关键词或正则表达式搜索，返回命中行及其上下文。

    Args:
        file_path: 日志文件绝对路径。
        keyword: 关键词；regex 为 True 时视为正则表达式。
        regex: 是否按正则匹配，默认 False（普通子串匹配）。
        context: 每个命中前后展示的上下文行数，默认 2。
        max_results: 最多返回的命中组数，默认 50。
    """
    return log_reader.search_log_keyword(
        file_path, keyword, regex=regex, context=context, max_results=max_results
    )


@mcp.tool()
def filter_log_by_level(file_path: str, level: str = "ERROR") -> str:
    """按日志级别筛选记录并统计条数；筛选某级别时会同时包含更严重级别。

    Args:
        file_path: 日志文件绝对路径。
        level: 目标级别，可选 FATAL/ERROR/WARN/INFO/DEBUG/TRACE，默认 ERROR。
    """
    return log_reader.filter_log_by_level(file_path, level=level)


@mcp.tool()
def get_log_stats(file_path: str) -> str:
    """生成日志统计报告：文件大小、总行数、时间范围、级别分布、高频错误 Top5。

    Args:
        file_path: 日志文件绝对路径。
    """
    return log_reader.get_log_stats(file_path)


@mcp.tool()
def analyze_log(file_path: str, max_lines: int = 0) -> str:
    """智能分析日志：自动抽取错误，给出根因、证据与修复建议。

    优先使用本地 Ollama 大模型；未安装或未启动时自动降级为内置规则引擎。

    Args:
        file_path: 日志文件绝对路径。
        max_lines: 送入分析的最大日志行数，0 表示使用配置默认值（400）。
    """
    return log_analyzer.analyze_log(file_path, max_lines=max_lines)


@mcp.tool()
def analyze_error_text(error_text: str) -> str:
    """对用户直接粘贴的一段报错/堆栈文本进行智能根因分析（无需日志文件）。

    Args:
        error_text: 报错信息或异常堆栈原文。
    """
    return log_analyzer.analyze_error_text(error_text)


@mcp.tool()
def check_llm_status() -> str:
    """检查本地 Ollama 服务与模型是否可用；不可用时会提示安装命令与降级状态。"""
    return log_analyzer.check_llm_status()


def main() -> None:
    """以 stdio 传输模式启动 MCP 服务（AI Agent 标准接入方式）。"""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
