"""端到端验证脚本：以 stdio 方式启动 MCP server，完成握手并真实调用工具。

运行方式（在项目根目录）：
    python examples/test_client.py

验证项：
1. MCP 协议初始化握手；
2. tools/list 能列出全部注册工具；
3. 真实调用 check_llm_status、get_log_stats、analyze_log 三个工具。
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def extract_text(result) -> str:
    """从 CallToolResult 中提取文本内容。"""
    parts = []
    for block in result.content:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts)


async def main() -> int:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-u", "src/server.py"],
        cwd=str(PROJECT_ROOT),
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            # 兼容 mcp 1.x 的 camelCase 与 2.x 的 snake_case
            server_info = getattr(init, "server_info", None) or getattr(init, "serverInfo")
            print(f"[1/4] MCP 握手成功，server: {server_info.name} "
                  f"v{server_info.version}")

            tools = await session.list_tools()
            names = [t.name for t in tools.tools]
            print(f"[2/4] 发现 {len(names)} 个工具：{', '.join(names)}")
            expected = {
                "list_log_files", "read_log_tail", "read_log_head",
                "search_log_keyword", "filter_log_by_level", "get_log_stats",
                "analyze_log", "analyze_error_text", "check_llm_status",
            }
            missing = expected - set(names)
            if missing:
                print(f"[失败] 缺少工具：{missing}")
                return 1

            status = await session.call_tool("check_llm_status", {})
            print(f"[3/4] check_llm_status =>\n{extract_text(status)}\n")

            sample = str(PROJECT_ROOT / "examples" / "sample.log")
            stats = await session.call_tool("get_log_stats", {"file_path": sample})
            print(f"[4/4] get_log_stats =>\n{extract_text(stats)}\n")

            analysis = await session.call_tool("analyze_log", {"file_path": sample})
            print(f"[附加] analyze_log =>\n{extract_text(analysis)[:1500]}\n")

            gz_sample = PROJECT_ROOT / "examples" / "sample.log.gz"
            if gz_sample.exists():
                gz_stats = await session.call_tool(
                    "get_log_stats", {"file_path": str(gz_sample)}
                )
                text = extract_text(gz_stats)
                assert "压缩包" in text and "ERROR=10" in text, "gzip 统计结果不符合预期"
                print(f"[5/5] gzip 压缩日志读取成功：\n{text}\n")

    print("✅ 端到端验证全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
