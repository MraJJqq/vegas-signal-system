from __future__ import annotations

import json
import os
import re
import urllib.request
from typing import Any
from urllib.parse import urlparse

CANDIDATE_STATUSES = {"ENTRY_SIGNAL_LONG", "ENTRY_SIGNAL_SHORT"}
DEFAULT_NTFY_BASE_URL = "https://ntfy.sh"


def _format_message(observations: list[dict[str, Any]], test: bool = False) -> str:
    if test:
        return "Vegas信号系统 ntfy 推送测试成功。当前仅测试通知通道，不代表存在交易信号。"
    lines = ["Vegas 正式候选信号"]
    for item in observations:
        lines.extend([
            f"{item.get('symbol_name', item.get('symbol_id', '未知品种'))} ({item.get('symbol_id', '')})",
            f"- 信号：{item.get('status', '')}",
            f"- 方向：4H {item.get('direction_4h', 'unavailable')} / 8H {item.get('direction_8h', 'unavailable')}",
            f"- 观察周期：{item.get('entry_timeframe') or '无'}",
            f"- 最新价：{item.get('close') if item.get('close') is not None else '无'}",
            f"- 时间：{item.get('timestamp') or '无'}",
            f"- 说明：{item.get('message', '')}",
            "",
        ])
    lines.append("信号在完整K线收盘后确认；系统只推送，不自动下单。")
    return "\n".join(lines)


def send_ntfy(topic: str, title: str, message: str, base_url: str | None = None,
              timeout: int = 10) -> dict[str, Any]:
    """Publish a message to ntfy using its JSON API."""
    topic = topic.strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{24,128}", topic):
        raise ValueError("NTFY_TOPIC 格式无效：请使用至少24位随机字符")
    base = (base_url or os.environ.get("NTFY_BASE_URL", DEFAULT_NTFY_BASE_URL)).strip().rstrip("/")
    parsed = urlparse(base)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("NTFY_BASE_URL 必须是有效的 HTTPS 服务地址")
    payload = json.dumps(
        {"topic": topic, "title": title.strip(), "message": message},
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        base, data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        status = getattr(response, "status", 200)
        if status < 200 or status >= 300:
            raise RuntimeError(f"ntfy 推送失败：HTTP {status}")
        body = response.read().decode("utf-8", errors="replace")
    return {"status": status, "response": body}


def notify_observations(observations, settings: dict[str, Any] | None = None) -> str:
    settings = settings or {}
    if not settings.get("enabled", False):
        return "通知未启用。"
    provider = str(settings.get("provider", "none")).lower()
    if provider != "ntfy":
        return f"未发送通知：不支持的通知渠道 {provider!r}。"
    secret_name = str(settings.get("topic_env", "NTFY_TOPIC"))
    topic = os.environ.get(secret_name, "").strip()
    if not topic:
        return f"未发送通知：请在 GitHub 仓库 Secrets 中设置 {secret_name}。"
    records = observations.to_dict(orient="records") if hasattr(observations, "to_dict") else list(observations)
    candidates = [item for item in records if item.get("status") in CANDIDATE_STATUSES]
    if not candidates:
        return "本轮没有符合过滤线条件的正式信号，未发送 ntfy 通知。"
    send_ntfy(topic, f"Vegas进场信号：{len(candidates)} 条", _format_message(candidates))
    return f"ntfy 通知已发送：{len(candidates)} 条过滤线信号。"


def send_test_notification(settings: dict[str, Any] | None = None) -> str:
    settings = settings or {}
    if not settings.get("enabled", False):
        return "通知未启用。"
    if str(settings.get("provider", "none")).lower() != "ntfy":
        return "未发送测试通知：当前通知渠道不是 ntfy。"
    secret_name = str(settings.get("topic_env", "NTFY_TOPIC"))
    topic = os.environ.get(secret_name, "").strip()
    if not topic:
        return f"未发送测试通知：请先在 GitHub 仓库 Secrets 中设置 {secret_name}。"
    send_ntfy(topic, "Vegas信号系统推送测试", _format_message([], test=True))
    return "ntfy 推送测试请求已成功提交。请检查 iPad 上的 ntfy App 是否收到通知。"
