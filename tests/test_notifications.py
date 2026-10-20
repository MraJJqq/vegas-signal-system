from unittest.mock import MagicMock, patch

from vegas_signal_system.notifications import notify_observations, send_test_notification


def test_notification_disabled_does_not_send():
    with patch("vegas_signal_system.notifications.send_ntfy") as send:
        assert notify_observations([], {"enabled": False, "provider": "ntfy"}) == "通知未启用。"
        send.assert_not_called()


def test_no_candidates_does_not_send(monkeypatch):
    monkeypatch.setenv("NTFY_TOPIC", "a" * 32)
    with patch("vegas_signal_system.notifications.send_ntfy") as send:
        result = notify_observations(
            [{"symbol_id": "BTC", "status": "WATCH_ENTRY_CONDITIONS"}],
            {"enabled": True, "provider": "ntfy"},
        )
        assert "没有 EMA144 触碰观察候选" in result
        send.assert_not_called()


def test_candidate_sends_notification(monkeypatch):
    monkeypatch.setenv("NTFY_TOPIC", "a" * 32)
    candidate = {
        "symbol_id": "BTC", "symbol_name": "比特币",
        "status": "WATCH_ENTRY_CONFIRMATION", "direction_4h": "up",
        "direction_8h": "up", "entry_timeframe": "1h", "close": 65000.0,
        "timestamp": "2026-10-20T10:00:00+00:00", "message": "触碰EMA144",
    }
    with patch("vegas_signal_system.notifications.send_ntfy") as send:
        result = notify_observations([candidate], {"enabled": True, "provider": "ntfy"})
        assert "1 条" in result
        assert "比特币" in send.call_args.args[2]


def test_test_notification_sends_test_message(monkeypatch):
    monkeypatch.setenv("NTFY_TOPIC", "b" * 32)
    with patch("vegas_signal_system.notifications.send_ntfy") as send:
        result = send_test_notification({"enabled": True, "provider": "ntfy"})
        assert "已成功提交" in result
        assert "不代表存在交易信号" in send.call_args.args[2]


def test_missing_secret_is_reported(monkeypatch):
    monkeypatch.delenv("NTFY_TOPIC", raising=False)
    assert "NTFY_TOPIC" in send_test_notification({"enabled": True, "provider": "ntfy"})


def test_ntfy_json_api_and_success():
    import json
    from vegas_signal_system.notifications import send_ntfy
    response = MagicMock()
    response.status = 200
    response.read.return_value = b'{"id":"abc"}'
    response.__enter__.return_value = response
    with patch("vegas_signal_system.notifications.urllib.request.urlopen", return_value=response) as urlopen:
        result = send_ntfy("c" * 32, "Test title", "Body")
        assert result["status"] == 200
        req = urlopen.call_args.args[0]
        assert req.full_url == "https://ntfy.sh"
        payload = json.loads(req.data.decode("utf-8"))
        assert payload["topic"] == "c" * 32
        assert payload["title"] == "Test title"
        assert payload["message"] == "Body"


def test_rejects_guessable_topic():
    import pytest
    from vegas_signal_system.notifications import send_ntfy
    with pytest.raises(ValueError, match="NTFY_TOPIC"):
        send_ntfy("vegas", "Test", "Body")


def test_rejects_non_https_base_url():
    import pytest
    from vegas_signal_system.notifications import send_ntfy
    with pytest.raises(ValueError, match="HTTPS"):
        send_ntfy("d" * 32, "Test", "Body", base_url="http://example.com")
