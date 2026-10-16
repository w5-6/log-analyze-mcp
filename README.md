# LogAnalyze-MCP

> 基于 **MCP（Model Context Protocol）** 的本地日志智能分析服务，让 Cursor / Claude Code / Trae 等 AI Agent 直接读取、筛选、统计并**自动诊断**你的日志文件。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

## 为什么做这个项目

排查线上问题时，开发者通常要反复执行「打开日志 → 找 ERROR → 搜关键词 → 看堆栈 → 百度报错」。
LogAnalyze-MCP 把这套流程封装成标准 MCP 工具，AI Agent 用一句自然语言就能自主完成排查，并给出根因与修复建议。

- 🔒 **纯本地运行**：日志文件不离开本机，基于 stdio 通信
- 🧠 **双引擎分析**：本地 Ollama 大模型语义分析 + 内置规则引擎兜底（**未装 Ollama 也能用**）
- 📦 **零配置上手**：9 个工具覆盖日志排查 80% 日常场景
- 🪶 **轻量无依赖**：仅需 Python，流式读取 GB 级大日志不爆内存
- 🗜️ **压缩日志直读**：透明支持 `.gz`（如 `app.log.gz`）与 `.zip`（支持多成员），无需先手动解压

## 功能一览（9 个 MCP 工具）

| 工具 | 作用 |
| --- | --- |
| `list_log_files` | 列出目录下日志文件（含 `.gz`/`.zip`，大小/修改时间，支持递归） |
| `read_log_tail` | 读取日志末尾 N 行（恒定内存，适合超大文件） |
| `read_log_head` | 读取日志开头 N 行（查看启动信息） |
| `search_log_keyword` | 关键词/正则搜索，带回溯上下文 |
| `filter_log_by_level` | 按 FATAL/ERROR/WARN 等级别筛选并计数 |
| `get_log_stats` | 统计报告：行数、时间范围、级别分布、高频错误 Top5 |
| `analyze_log` | **智能诊断**：抽取错误 → 根因分析 → 修复建议 |
| `analyze_error_text` | 直接分析粘贴的报错/堆栈片段 |
| `check_llm_status` | 检查 Ollama 连接与模型状态 |

## 快速开始

### 1. 环境要求

- Python 3.10+
- （可选）[Ollama](https://ollama.com/download)：启用大模型语义分析；不安装则使用规则引擎

### 2. 获取代码并安装依赖

```bash
git clone https://github.com/<your-name>/log-analyze-mcp.git
cd log-analyze-mcp

# 建议使用虚拟环境
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 3.（可选）启用本地大模型

```bash
# 安装 Ollama 后拉取模型（CPU 可选 3b/1.5b，追求效果选 7b）
ollama pull qwen2.5:7b
```

如需自定义，复制 `.env.example` 为 `.env`，修改 `OLLAMA_BASE_URL`、`OLLAMA_MODEL`。

### 4. 验证安装

```bash
# 单元测试（不依赖 MCP/Ollama）
python tests/test_tools.py

# 端到端验证：启动 MCP server → 握手 → 真实调用工具
python examples/test_client.py
```

## 接入 AI Agent

### Cursor

`Settings → Features → MCP → Add new MCP server`，填入（路径替换为本机实际路径）：

```json
{
  "mcpServers": {
    "log-analyze": {
      "command": "python",
      "args": ["-u", "src/server.py"],
      "cwd": "C:/path/to/log-analyze-mcp",
      "env": {
        "OLLAMA_MODEL": "qwen2.5:7b"
      }
    }
  }
}
```

完整模板见 [`examples/cursor-config.json`](examples/cursor-config.json)。

### Claude Code / Claude Desktop

复制 [`examples/claude-code-mcp.json`](examples/claude-code-mcp.json) 中的 `mcpServers` 段到项目 `.mcp.json` 或 `claude_desktop_config.json`。

## 使用示例

接入后，直接在 Agent 对话框用自然语言：

- 「帮我看看 `D:/logs` 目录下有哪些日志文件」
- 「分析一下 `app.log` 最近的错误，告诉我根因和修复方案」
- 「搜索日志里所有 `timeout` 相关记录，带 3 行上下文」
- 「统计这个日志里 ERROR 和 WARN 各有多少条」

Agent 会自动编排工具调用链：
`list_log_files → get_log_stats → filter_log_by_level → analyze_log`，最终输出结构化诊断报告。

## 工作原理

```
┌──────────────┐   stdio / JSON-RPC    ┌──────────────────────┐      HTTP       ┌──────────┐
│  AI Agent    │ ◀──────────────────▶ │  LogAnalyze-MCP      │ ◀─────────────▶ │  Ollama  │
│ Cursor / CC  │   tools/call          │  (FastMCP Server)    │   (本地，可选)   │ 本地大模型 │
└──────────────┘                       │  9 个日志分析工具      │                  └──────────┘
                                       │  规则引擎（兜底）      │
                                       └──────────────────────┘
                                                 │ 只读
                                                 ▼
                                       本地日志文件（不上传）
```

1. AI Agent 作为 MCP Host，通过 stdio 启动本服务并完成能力协商；
2. Agent 自主规划排查步骤，按需调用工具；
3. 工具流式读取本地日志，返回结构化文本；
4. 诊断类工具调用本地 Ollama 生成根因分析；Ollama 不可用时自动降级为规则引擎。

## 项目结构

```
log-analyze-mcp/
├── src/
│   ├── server.py            # MCP 服务入口（FastMCP，9 个工具）
│   ├── config.py            # 配置加载（环境变量 > config.json > 默认值）
│   ├── tools/
│   │   ├── log_reader.py    # 日志读取/搜索/筛选/统计
│   │   └── log_analyzer.py  # 智能诊断编排
│   └── llm/
│       └── ollama_client.py # Ollama 客户端 + 规则引擎
├── examples/
│   ├── sample.log           # 演示用样例日志
│   ├── test_client.py       # 端到端验证脚本
│   ├── cursor-config.json
│   └── claude-code-mcp.json
├── tests/test_tools.py
├── requirements.txt
└── config.json
```

## 安全与合规说明

- 本工具仅做**本地只读**日志分析，不会修改、删除、上传任何文件；
- 请仅在你有权限访问的机器与日志上使用；
- 规则引擎与大模型的分析结论仅供参考，生产环境请结合监控与代码复核。

## 路线图

- [x] 支持 gzip/zip 压缩日志直接读取（v1.1.0）
- [ ] 支持日志多格式自动解析（JSON Lines、自定义正则、logback 模板）
- [ ] 错误时间线视图与跨文件关联分析
- [ ] 支持 OpenAI 兼容接口（如内网 vLLM 部署）
- [ ] 可选 Web 看板（只读）

## License

[MIT License](LICENSE)
