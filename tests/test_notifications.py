from unittest.mock import patch

from vegas_signal_system.notifications import notify_observations, send_test_notification


def test_notification_disabled_does_not_send():
    with patch("vegas_signal_system.notifications.send_wecom_markdown") as send:
        assert notify_observations([], {"enabled": False, "provider": "wecom_bot"}) == "通知未启用。"
        send.assert_not_called()


def test_no_candidates_does_not_send(monkeypatch):
    monkeypatch.setenv("WECHAT_WORK_WEBHOOK", "https://example.invalid/webhook")
    with patch("vegas_signal_system.notifications.send_wecom_markdown") as send:
        result = notify_observations(
            [{"symbol_id": "NVDA", "status": "WATCH_ENTRY_CONDITIONS"}],
            {"enabled": True, "provider": "wecom_bot"},
        )
        assert "没有 EMA144 触碰观察候选" in result
        send.assert_not_called()


def test_candidate_sends_notification(monkeypatch):
    monkeypatch.setenv("WECHAT_WORK_WEBHOOK", "https://example.invalid/webhook")
    candidate = {
        "symbol_id": "NVDA", "symbol_name": "英伟达",
        "status": "WATCH_ENTRY_CONFIRMATION", "direction_4h": "up",
        "direction_8h": "up", "entry_timeframe": "1h", "close": 150.0,
        "timestamp": "2026-10-20T10:00:00+00:00", "message": "触碰EMA144",
    }
    with patch("vegas_signal_system.notifications.send_wecom_markdown") as send:
        result = notify_observations([candidate], {"enabled": True, "provider": "wecom_bot"})
        assert "1 条" in result
        assert "英伟达" in send.call_args.args[1]


def test_test_notification_sends_test_message(monkeypatch):
    monkeypatch.setenv("WECHAT_WORK_WEBHOOK", "https://example.invalid/webhook")
    with patch("vegas_signal_system.notifications.send_wecom_markdown") as send:
        result = send_test_notification({"enabled": True, "provider": "wecom_bot"})
        assert "已发送" in result
        assert "不代表存在交易信号" in send.call_args.args[1]


def test_missing_secret_is_reported(monkeypatch):
    monkeypatch.delenv("WECHAT_WORK_WEBHOOK", raising=False)
    assert "WECHAT_WORK_WEBHOOK" in send_test_notification(
        {"enabled": True, "provider": "wecom_bot"}
    )
