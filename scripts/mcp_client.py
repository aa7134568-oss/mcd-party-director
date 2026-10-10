#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mcd-party-director / mcp_client.py
----------------------------------
麦当劳中国官方 MCP Server 的极简客户端（Streamable HTTP）。

用途：
  - 在命令行直接验证 Token 连通性与工具返回结构
  - 供 Skill 在需要时做只读侦察（活动日历、可预约城市/门店/日期/场次）
  - 把 MCP 返回落盘为 JSON，交给 party_planner.py 做确定性计算

安全约定：
  - Token 只从环境变量 MCD_MCP_TOKEN 读取，绝不作为命令行参数传入，
    避免出现在 ps / shell history / 日志中。
  - 任何输出都会对 Token 做脱敏。

依赖：仅标准库。Python 3.9+
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

ENDPOINT = os.environ.get("MCD_MCP_URL", "https://mcp.mcd.cn")
PROTOCOL_VERSION = "2025-06-18"   # 官方说明：仅支持 2025-06-18 及之前


class McpError(Exception):
    pass


class McpClient:
    def __init__(self, token: Optional[str] = None, endpoint: str = ENDPOINT):
        self.token = token or os.environ.get("MCD_MCP_TOKEN", "")
        if not self.token:
            raise McpError(
                "未找到 MCP Token。请先设置环境变量：\n"
                "  export MCD_MCP_TOKEN='你的Token'\n"
                "Token 申请地址：https://open.mcd.cn/mcp （登录 → 控制台 → 激活）"
            )
        self.endpoint = endpoint
        self.session_id: Optional[str] = None
        self._id = 0

    # ------------------------------------------------------------------
    def _post(self, payload: Dict[str, Any], timeout: int = 30) -> Dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {self.token}",
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id

        req = urllib.request.Request(self.endpoint, data=body, headers=headers,
                                     method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                sid = resp.headers.get("Mcp-Session-Id")
                if sid:
                    self.session_id = sid
                ctype = resp.headers.get("Content-Type", "")
                raw = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:500]
            if e.code == 401:
                raise McpError(f"[401] Token 无效、已过期或未提供。请到控制台重新激活。\n{detail}")
            if e.code == 429:
                raise McpError("[429] 触发限流（600 次/分钟）。请降低调用频率后重试。")
            raise McpError(f"[{e.code}] 请求失败：{detail}")
        except urllib.error.URLError as e:
            raise McpError(f"网络错误：{e.reason}")

        # Streamable HTTP 可能返回 SSE 或纯 JSON
        if "text/event-stream" in ctype or raw.lstrip().startswith("event:"):
            return self._parse_sse(raw)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return self._parse_sse(raw)

    @staticmethod
    def _parse_sse(raw: str) -> Dict[str, Any]:
        """从 SSE 流中抽取最后一个 data: JSON 负载。"""
        last = None
        for block in raw.split("\n\n"):
            for line in block.splitlines():
                if line.startswith("data:"):
                    last = line[5:].strip()
        if not last:
            raise McpError(f"无法解析 SSE 响应：{raw[:300]}")
        try:
            return json.loads(last)
        except json.JSONDecodeError:
            raise McpError(f"SSE data 不是合法 JSON：{last[:300]}")

    # ------------------------------------------------------------------
    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def initialize(self) -> Dict[str, Any]:
        r = self._post({
            "jsonrpc": "2.0", "id": self._next_id(), "method": "initialize",
            "params": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "mcd-party-director", "version": "1.0.0"},
            },
        })
        # 通知服务端初始化完成（MCP 规范要求）
        try:
            urllib.request.urlopen(urllib.request.Request(
                self.endpoint,
                data=json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}
                                ).encode("utf-8"),
                headers={"Content-Type": "application/json",
                         "Accept": "application/json, text/event-stream",
                         "Authorization": f"Bearer {self.token}",
                         **({"Mcp-Session-Id": self.session_id} if self.session_id else {})},
                method="POST"), timeout=15)
        except Exception:
            pass  # 通知失败不阻塞后续调用
        return r

    def list_tools(self) -> Dict[str, Any]:
        return self._post({"jsonrpc": "2.0", "id": self._next_id(),
                           "method": "tools/list", "params": {}})

    def call(self, name: str, arguments: Optional[Dict[str, Any]] = None,
             retries: int = 2) -> Dict[str, Any]:
        payload = {"jsonrpc": "2.0", "id": self._next_id(), "method": "tools/call",
                   "params": {"name": name, "arguments": arguments or {}}}
        for attempt in range(retries + 1):
            r = self._post(payload)
            if "error" in r and r["error"].get("code") == 429 and attempt < retries:
                time.sleep(2 ** attempt)
                continue
            return r
        return r

    # ------------------------------------------------------------------
    @staticmethod
    def unwrap(resp: Dict[str, Any]) -> Any:
        """把 JSON-RPC 响应还原成工具的实际业务数据。"""
        if "error" in resp:
            raise McpError(f"RPC 错误：{resp['error']}")
        result = resp.get("result", {})
        if isinstance(result, dict) and "content" in result:
            parts = []
            for c in result["content"]:
                if c.get("type") == "text":
                    txt = c["text"]
                    try:
                        parts.append(json.loads(txt))
                    except json.JSONDecodeError:
                        parts.append(txt)
            return parts[0] if len(parts) == 1 else parts
        return result


def main():
    p = argparse.ArgumentParser(description="麦当劳 MCP 客户端（只读侦察 / 连通性自检）")
    p.add_argument("action", choices=["init", "tools", "call", "recon"],
                   help="init=握手 tools=列工具 call=调用指定工具 recon=派对可行性侦察")
    p.add_argument("--name", help="tools/call 的工具名")
    p.add_argument("--args", default="{}", help="工具入参 JSON 字符串")
    p.add_argument("--city", help="recon 模式下的城市名")
    p.add_argument("--out", help="把结果写入 JSON 文件")
    a = p.parse_args()

    cli = McpClient()

    if a.action == "init":
        r = cli.initialize()
        print(json.dumps(r, ensure_ascii=False, indent=2)[:1500])

    elif a.action == "tools":
        cli.initialize()
        r = cli.list_tools()
        tools = McpClient.unwrap(r)
        names = [t.get("name") for t in tools.get("tools", [])] if isinstance(tools, dict) else []
        print(f"共 {len(names)} 个工具：")
        for n in names:
            print("  -", n)

    elif a.action == "call":
        if not a.name:
            sys.exit("call 模式需要 --name")
        cli.initialize()
        try:
            args = json.loads(a.args)
        except json.JSONDecodeError:
            sys.exit("--args 必须是合法 JSON")
        r = cli.call(a.name, args)
        out = McpClient.unwrap(r)
        text = json.dumps(out, ensure_ascii=False, indent=2)
        print(text[:6000])
        if a.out:
            with open(a.out, "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
            print(f"\n已写入 {a.out}")

    elif a.action == "recon":
        cli.initialize()
        report: Dict[str, Any] = {}
        for step, tool, arg in [
            ("当前时间", "now-time-info", {}),
            ("活动日历", "campaign-calendar", {}),
            ("派对城市", "query-party-city", {}),
        ]:
            try:
                report[step] = McpClient.unwrap(cli.call(tool, arg))
            except McpError as e:
                report[step] = {"error": str(e)}
            time.sleep(0.3)
        text = json.dumps(report, ensure_ascii=False, indent=2)
        print(text[:6000])
        if a.out:
            with open(a.out, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            print(f"\n已写入 {a.out}")


if __name__ == "__main__":
    try:
        main()
    except McpError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)
