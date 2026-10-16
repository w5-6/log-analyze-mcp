"""Ollama 本地大模型客户端封装。

- 优先调用本地 Ollama（/api/generate），日志数据不出本机；
- 当 Ollama 未安装 / 未启动 / 模型未拉取时，自动降级为内置规则分析，
  保证 MCP 工具在任何环境下都能给出可用结果。
"""
from __future__ import annotations

import re
from typing import Optional

import httpx

from src.config import CONFIG


class OllamaClient:
    """轻量 Ollama REST 客户端（仅依赖 httpx，无需官方 SDK）。"""

    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None,
                 timeout: Optional[int] = None) -> None:
        self.base_url = (base_url or CONFIG["ollama_base_url"]).rstrip("/")
        self.model = model or CONFIG["ollama_model"]
        self.timeout = timeout or int(CONFIG["ollama_timeout"])

    def health_check(self) -> tuple[bool, str]:
        """返回 (是否可用, 状态说明)。"""
        try:
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=5)
            resp.raise_for_status()
            models = [m.get("name", "") for m in resp.json().get("models", [])]
            if self.model in models or any(m.startswith(self.model) for m in models):
                return True, f"Ollama 在线，模型 {self.model} 可用"
            return False, (
                f"Ollama 在线，但未找到模型 {self.model}。"
                f"已安装模型：{', '.join(models) if models else '无'}；"
                f"请执行 `ollama pull {self.model}`"
            )
        except httpx.ConnectError:
            return False, (
                f"无法连接 Ollama（{self.base_url}）。"
                "请先安装并启动 Ollama：https://ollama.com/download ，"
                f"然后执行 `ollama pull {self.model}`"
            )
        except Exception as exc:  # noqa: BLE001 - 状态检查需吞掉所有异常
            return False, f"Ollama 状态检查失败：{exc}"

    def generate(self, prompt: str, system: str = "") -> str:
        """调用 Ollama 生成文本，失败时抛出异常。"""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {"temperature": 0.2},
        }
        resp = httpx.post(
            f"{self.base_url}/api/generate", json=payload, timeout=self.timeout
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()


# ----------------------------------------------------------------------------
# 内置规则分析（降级方案 + 无模型时的即时分析）
# ----------------------------------------------------------------------------

# 每条规则：(匹配正则列表, 可能原因, 排查/修复建议)
_RULES: list[tuple[list[str], str, str]] = [
    (
        [r"connection refused", r"connection reset", r"连接被拒绝", r"连接已重置"],
        "目标服务未启动、端口错误，或防火墙拦截了连接。",
        "1) 确认下游服务/数据库已启动并监听对应端口；2) 核对 host/port 配置；"
        "3) 用 telnet/nc/curl 测试端口连通性；4) 检查防火墙与安全组规则。",
    ),
    (
        [r"timed?\s?out", r"timeout", r"超时"],
        "请求在规定时间内未得到响应，可能是网络抖动、服务过载或查询太慢。",
        "1) 检查目标服务负载与慢查询；2) 适当调大超时时间；3) 检查网络延迟与 DNS；"
        "4) 为耗时操作增加重试与熔断。",
    ),
    (
        [r"nullpointerexception", r"nonetype", r"cannot read propert\w* of null",
         r"null reference"],
        "代码访问了值为 null/None 的对象，通常缺少空值判断。",
        "1) 定位报错堆栈最顶层的业务代码行；2) 对可能为空的返回值/字段加空值判断；"
        "3) 检查上游接口返回结构是否发生变化。",
    ),
    (
        [r"outofmemory", r"out of memory", r"oom", r"memoryerror", r"内存不足",
         r"cannot allocate memory"],
        "内存溢出：堆内存不足、存在内存泄漏，或一次性加载了过大的数据。",
        "1) 增大 JVM/进程内存上限；2) 排查大对象/集合是否未释放（内存泄漏）；"
        "3) 大文件改成分批/流式读取；4) 观察 GC 与内存曲线。",
    ),
    (
        [r"permission denied", r"access is denied", r"权限不足", r"拒绝访问"],
        "进程对目标文件/端口/资源没有访问权限。",
        "1) 检查文件属主与读写权限（chmod/chown）；2) Linux 下非 root 不能监听 1024 以下端口；"
        "3) Windows 下尝试以管理员身份运行；4) 检查安全软件拦截。",
    ),
    (
        [r"no module named", r"modulenotfounderror", r"importerror",
         r"cannot find module", r"找不到模块"],
        "缺少依赖包，或依赖未安装到当前运行的 Python/Node 环境。",
        "1) 用当前解释器执行 pip install <包名>；2) 确认虚拟环境已激活；"
        "3) 检查包名拼写与 requirements.txt 是否完整。",
    ),
    (
        [r"no such file", r"filenotfounderror", r"cannot find the file",
         r"系统找不到指定的文件"],
        "引用的文件/路径不存在，常见于相对路径错误或配置文件未部署。",
        "1) 打印并核对实际读取的绝对路径；2) 检查工作目录是否与预期一致；"
        "3) 部署时确认配置/资源文件已随包发布。",
    ),
    (
        [r"no space left", r"disk full", r"磁盘空间不足", r"enospc"],
        "磁盘空间已满，日志写入、文件上传或临时文件创建失败。",
        "1) 清理日志/临时文件与容器镜像；2) 配置日志轮转（logrotate）；"
        "3) 扩容磁盘或挂载新数据盘；4) 检查是否有异常狂刷日志的死循环。",
    ),
    (
        [r"address already in use", r"端口.*占用", r"bind:.*(in use|eaddrinuse)"],
        "服务要监听的端口已被其他进程占用（常见于旧进程未退出）。",
        "1) 查找占用进程：lsof -i:端口 / netstat -ano | findstr 端口；"
        "2) 结束残留进程或更换端口；3) 排查是否重复启动了多个实例。",
    ),
    (
        [r"unauthori[sz]ed", r"\b401\b", r"authentication failed", r"认证失败"],
        "身份认证失败：凭证缺失、过期或错误。",
        "1) 核对 token/账号密码/API Key；2) 检查凭证是否过期；"
        "3) 确认请求头 Authorization 格式正确（Bearer 等）。",
    ),
    (
        [r"forbidden", r"\b403\b", r"无权限访问"],
        "已通过认证但没有该资源的访问权限（403）。",
        "1) 检查账号角色/权限策略（RBAC）；2) 确认资源归属与授权范围；"
        "3) 检查服务端 ACL、IP 白名单。",
    ),
    (
        [r"\b404\b", r"not found", r"不存在"],
        "请求的资源或接口不存在（404）。",
        "1) 核对 URL 路径与版本前缀（/api/v1）；2) 确认服务已注册该路由；"
        "3) 检查网关/反向代理的 path 转发规则。",
    ),
    (
        [r"\b502\b", r"bad gateway"],
        "网关从上游服务收到了无效响应（502），通常是上游服务宕机或协议错误。",
        "1) 检查上游服务是否存活；2) 查看上游日志；3) 检查网关与上游的协议/超时配置。",
    ),
    (
        [r"\b503\b", r"service unavailable", r"服务不可用"],
        "服务暂时不可用（503）：服务过载、正在重启或被限流。",
        "1) 检查服务实例数与健康检查；2) 查看 CPU/内存负载；3) 确认发布/重启是否刚结束。",
    ),
    (
        [r"ssl certificate", r"certificate verify failed", r"证书"],
        "SSL/TLS 证书校验失败：证书过期、自签名或 CA 不受信任。",
        "1) 检查证书有效期与域名是否匹配；2) 更新 CA 证书；"
        "3) 内网自签名证书需显式配置信任（切勿在生产简单关闭校验）。",
    ),
    (
        [r"name or service not known", r"unknown host", r"dns", r"getaddrinfo failed",
         r"无法解析"],
        "域名解析失败（DNS 问题）。",
        "1) 用 nslookup/dig 验证域名解析；2) 检查 /etc/hosts 与 DNS 配置；"
        "3) 确认内网域名在当前网络可解析。",
    ),
    (
        [r"keyerror", r"undefined column", r"unknown column"],
        "访问了字典中不存在的键 / 数据表中不存在的列。",
        "1) 打印实际数据的键集合；2) 用 .get() 提供默认值；"
        "3) 核对数据库表结构与字段名是否随版本变更。",
    ),
    (
        [r"indexerror", r"index out of range", r"越界"],
        "数组/列表下标越界。",
        "1) 检查列表是否为空；2) 访问前校验下标与长度；3) 排查分页边界条件。",
    ),
    (
        [r"segmentation fault", r"segfault", r"access violation", r"段错误"],
        "原生程序访问了非法内存（段错误），常见于 C/C++ 扩展、驱动或 ABI 不兼容。",
        "1) 记录崩溃时的 core dump 并用 gdb 分析；2) 排查最近升级的原生库/驱动；"
        "3) 检查是否存在内存踩踏或并发问题。",
    ),
    (
        [r"recursion", r"stackoverflowerror", r"栈溢出", r"maximum recursion depth"],
        "递归深度过大或无限递归导致栈溢出。",
        "1) 检查递归终止条件；2) 增大栈/递归深度上限（临时手段）；3) 改写为迭代实现。",
    ),
    (
        [r"deadlock", r"deadlock", r"死锁", r"lock wait timeout"],
        "多线程/数据库事务相互等待资源形成死锁。",
        "1) 统一多线程加锁顺序；2) 缩短事务、避免事务内等待外部调用；"
        "3) 数据库侧查看 innodb 锁等待并杀掉阻塞事务。",
    ),
    (
        [r"syntaxerror", r"语法错误", r"unexpected token"],
        "代码或配置文件存在语法错误。",
        "1) 定位报错文件与行号；2) 检查括号/引号/缩进（YAML/Python 缩进敏感）；"
        "3) 本地用解释器/校验器提前验证配置。",
    ),
]


def heuristic_analyze(error_text: str, stats: Optional[dict] = None) -> str:
    """基于内置规则库对错误日志做启发式分析（Ollama 不可用时的降级方案）。"""
    text = error_text.lower()
    matched: list[tuple[str, str, str]] = []
    seen_reasons: set[str] = set()

    for patterns, reason, advice in _RULES:
        for pat in patterns:
            if re.search(pat, text, flags=re.IGNORECASE):
                if reason not in seen_reasons:
                    matched.append((pat, reason, advice))
                    seen_reasons.add(reason)
                break

    lines = ["# 日志智能分析报告（内置规则引擎 · 未启用本地大模型）", ""]

    if stats:
        level_counts = stats.get("level_counts", {})
        total = stats.get("total_lines", 0)
        lines.append(f"- 日志总行数：{total}")
        if level_counts:
            order = ["FATAL", "ERROR", "WARN", "INFO", "DEBUG", "TRACE"]
            parts = [f"{lv}={level_counts.get(lv, 0)}" for lv in order if level_counts.get(lv, 0)]
            lines.append("- 级别分布：" + "，".join(parts))
        lines.append("")

    if not matched:
        lines.extend([
            "未匹配到已知的典型错误模式。建议：",
            "1) 提取报错堆栈的第一行与「Caused by」段落，它通常指向根因；",
            "2) 关注时间戳最早出现的第一条错误，后续错误多为连锁反应；",
            "3) 安装 Ollama 并拉取模型后可获得大模型的语义级根因分析。",
        ])
        return "\n".join(lines)

    lines.append(f"共识别出 {len(matched)} 类潜在问题：")
    lines.append("")
    for i, (_, reason, advice) in enumerate(matched, 1):
        lines.append(f"## 问题 {i}：{reason}")
        lines.append(f"**排查与修复建议：**")
        lines.append(advice)
        lines.append("")

    lines.append("> 提示：以上为规则匹配结果。安装 Ollama 后可结合上下文获得更精准的大模型分析。")
    return "\n".join(lines)
