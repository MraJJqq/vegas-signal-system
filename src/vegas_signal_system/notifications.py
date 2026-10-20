from __future__ import annotations

import json
import os
import re
import urllib.request
from typing import Any

CANDIDATE_STATUS = "WATCH_ENTRY_CONFIRMATION"


def _format_message(observations: list[dict[str, Any]], test: bool = False) -> str:
    if test:
        return "Vegas信号系统个人微信推送测试成功。当前仅测试通知通道，不代表存在交易信号。"
    lines = ["## Vegas 信号观察"]
    for item in observations:
        lines.extend([
            f"**{item.get('symbol_name', item.get('symbol_id', '未知品种'))} ({item.get('symbol_id', '')})**",
            f"- 状态：{item.get('status', '')}",
            f"- 方向：4H {item.get('direction_4h', 'unavailable')} / 8H {item.get('direction_8h', 'unavailable')}",
            f"- 观察周期：{item.get('entry_timeframe') or '无'}",
            f"- 最新价：{item.get('close') if item.get('close') is not None else '无'}",
            f"- 时间：{item.get('timestamp') or '无'}",
            f"- 说明：{item.get('message', '')}",
        ])
    lines.append("> 仅为观察提醒，不是正式进场信号；系统不会自动下单。")
    return "\n".join(lines)


def send_serverchan(sendkey: str, title: str, message: str, timeout: int = 10) -> dict[str, Any]:
    """Send a message using Server酱 Turbo (SCT) or Server酱³ (SC3)."""
    key = sendkey.strip()
    if not key:
        raise ValueError("Server酱 SendKey 为空")
    if key.startswith("sctp"):
        match = re.match(r"^sctp(\d+)t", key)
        if not match:
            raise ValueError("Server酱³ SendKey 格式无效")
        url = f"https://{match.group(1)}.push.ft07.com/send/{key}.send"
    else:
        url = f"https://sctapi.ftqq.com/{key}.send"
    payload = json.dumps({"title": title.replace("\\n", " ").strip(), "desp": message},
                         ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json;charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8", errors="replace")
    result = json.loads(body) if body else {}
    if result.get("code") != 0:
        # Do not include the SendKey or request URL in error text.
        raise RuntimeError(f"Server酱拒绝推送：code={result.get('code')}，message={result.get('message', '未知错误')}")
    return result


def notify_observations(observations, settings: dict[str, Any] | None = None) -> str:
    settings = settings or {}
    if not settings.get("enabled", False):
        return "通知未启用。"
    provider = str(settings.get("provider", "none")).lower()
    if provider != "serverchan":
        return f"未发送通知：不支持的通知渠道 {provider!r}。"
    secret_name = str(settings.get("sendkey_env", "SERVERCHAN_SENDKEY"))
    sendkey = os.environ.get(secret_name, "").strip()
    if not sendkey:
        return f"未发送通知：请在 GitHub 仓库 Secrets 中设置 {secret_name}。"
    records = observations.to_dict(orient="records") if hasattr(observations, "to_dict") else list(observations)
    candidates = [item for item in records if item.get("status") == CANDIDATE_STATUS]
    if not candidates:
        return "本轮没有 EMA144 触碰观察候选，未发送微信通知。"
    send_serverchan(sendkey, f"Vegas信号观察：{len(candidates)} 条候选", _format_message(candidates))
    return f"个人微信通知已发送：{len(candidates)} 条中锋触碰观察。"


def send_test_notification(settings: dict[str, Any] | None = None) -> str:
    settings = settings or {}
    if not settings.get("enabled", False):
        return "通知未启用。"
    if str(settings.get("provider", "none")).lower() != "serverchan":
        return "未发送测试通知：当前通知渠道不是 serverchan。"
    secret_name = str(settings.get("sendkey_env", "SERVERCHAN_SENDKEY"))
    sendkey = os.environ.get(secret_name, "").strip()
    if not sendkey:
        return f"未发送测试通知：请先在 GitHub 仓库 Secrets 中设置 {secret_name}。"
    send_serverchan(sendkey, "Vegas信号系统推送测试", _format_message([], test=True))
    return "个人微信推送测试请求已成功提交给 Server酱。请检查微信是否收到消息。"
