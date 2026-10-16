# LogAnalyze-MCP · GitHub 发布文案包

> 直接复制使用。仓库地址占位符 `https://github.com/<your-name>/log-analyze-mcp` 请替换为你的实际地址。

---

## 1. 仓库名称（Repository name）

```
log-analyze-mcp
```

## 2. 仓库简介（About / Description，二选一）

英文版（推荐，利于国际传播，约 150 字符）：

```
🪵 Local log analysis MCP server for AI agents (Cursor/Claude Code). Tail, search, filter, stats & root-cause diagnosis with local Ollama or a built-in rule engine.
```

中文版：

```
🪵 面向 AI Agent（Cursor/Claude Code）的本地日志分析 MCP 服务：读取、搜索、筛选、统计与根因诊断，支持本地 Ollama 或内置规则引擎，支持 gzip/zip 直读。
```

Website 字段可填：`https://github.com/<your-name>/log-analyze-mcp`（有博客后替换）

## 3. Topics 标签（GitHub 最多 20 个，逐个粘贴）

```
mcp
model-context-protocol
log-analysis
ai-agent
llm
ollama
cursor
claude-code
developer-tools
observability
sre
devops
troubleshooting
error-monitoring
local-first
python
cli
logs
artificial-intelligence
root-cause-analysis
```

## 4. Release Notes

### Release v1.1.0 — Compressed logs support（当前版本）

标题建议：`v1.1.0 - Read gzip/zip logs directly`

```markdown
## What's New 🗜️

- **Compressed logs, read directly**: transparently read `.gz` logs (e.g. `app.log.gz`) and `.zip` archives (multi-member supported) — no manual decompression needed.
- Compressed archives are auto-detected by `list_log_files`; tail/search/filter/stats/analyze all work on them.
- Compressed size is labeled in the stats report.

## 🔧 Compatibility

- Works on both `mcp` 1.x (FastMCP) and 2.x (MCPServer).
- 10 unit tests + an end-to-end stdio MCP handshake/call test all green.

## 中文说明

- 新增 gzip/zip 压缩日志透明读取（支持 zip 多成员），所有工具无需手动解压即可直接分析；
- 兼容 mcp 1.x / 2.x；10 个单元测试与端到端 MCP 验证全部通过。
```

### Release v1.0.0 — First release

标题建议：`v1.0.0 - Initial release`

```markdown
First release of LogAnalyze-MCP.

## ✨ Features

- 9 MCP tools: list/head/tail/search/filter/stats/analyze logs + check LLM status.
- Dual diagnosis engine: local Ollama LLM for semantic root-cause analysis, with a built-in rule engine fallback (works without Ollama).
- 100% local, stdio transport — logs never leave your machine.
- Streaming reads for large files; zero-config start with Python only.
- Ready-to-use configs for Cursor and Claude Code.
```

## 5. 各平台首发推广文案

### V2EX / 即刻 / 中文技术社区（长文）

```
做了个给 AI Agent 用的本地日志分析 MCP 服务：LogAnalyze-MCP

平时排查线上问题，总要反复「打开日志 → grep ERROR → 看堆栈 → 搜报错」。
于是我把这套流程封装成标准 MCP 工具，在 Cursor / Claude Code 里说一句
"帮我分析 app.log 最近的错误，给我根因和修复建议"，Agent 就会自己完成：
列文件 → 统计级别分布 → 筛错误 → 智能诊断。

特点：
- 9 个工具：列出/头尾读取/正则搜索/级别筛选/统计/智能诊断
- 双引擎：本地 Ollama 大模型分析；没装 Ollama 时内置规则引擎兜底（20+ 常见报错模式）
- 纯本地 stdio 通信，日志不出本机；流式读取，大文件不爆内存
- 支持 gzip/zip 压缩日志直接读
- 已在 mcp 1.x/2.x 上验证，含单元测试和端到端测试

GitHub：https://github.com/<your-name>/log-analyze-mcp
欢迎试用、提 issue 和 PR。
```

### X / Twitter（英文短文）

```
🪵 LogAnalyze-MCP: let Cursor / Claude Code diagnose your logs for you.

Tail, grep, filter, stats and AI root-cause analysis as 9 MCP tools.
Runs 100% locally — Ollama when available, a built-in rule engine when not.
Reads gzip/zip directly. MIT, Python.

https://github.com/<your-name>/log-analyze-mcp

#MCP #LLM #Ollama #SRE #DevTools
```

### Reddit r/mcp 或 r/ClaudeAI（英文，务实风格）

```
I built an MCP server for local log troubleshooting: tail, grep, filter, stats
and AI root-cause analysis across 9 tools. It works with Cursor and Claude Code
over stdio, stays fully local, uses Ollama if you have it and falls back to a
20+ pattern rule engine if you don't. It also reads gzip/zip logs directly.
MIT licensed, tested against mcp 1.x and 2.x. Feedback welcome.
```

## 6. 发布前检查清单

- [ ] 仓库名与 About 描述已填写
- [ ] 20 个 Topics 已添加
- [ ] README 中的 `<your-name>` 已替换，badge 正常显示
- [ ] 打 tag：`git tag v1.1.0 && git push origin v1.1.0`
- [ ] GitHub Releases 发布 v1.0.0 与 v1.1.0
- [ ] 准备一张 1280×640 的 social preview（建议：终端 + 日志诊断报告的截图）
- [ ] 首屏 README 放一张 30 秒演示 GIF（在 Cursor 中对话诊断日志的录屏）

## 7. 冷启动传播建议（低成本高回报）

1. **README 顶部放 30 秒演示 GIF**：MCP 类项目转化率最高的素材，没有之一。
2. **提交到 MCP 官方 servers 列表/精选仓库**（Awesome MCP Servers），这是 MCP 项目最大流量来源。
3. 发布后到 Cursor / Claude Code / Ollama 中文社区、V2EX「分享创造」节点同步。
4. Issue 区主动留 2-3 个「good first issue」标签（例如：支持 JSON Lines 日志、brotli 压缩），吸引早期 PR。
