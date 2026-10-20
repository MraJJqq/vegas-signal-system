from unittest.mock import patch

from vegas_signal_system.notifications import notify_observations, send_test_notification


def test_notification_disabled_does_not_send():
    with patch("vegas_signal_system.notifications.send_serverchan") as send:
        assert notify_observations([], {"enabled": False, "provider": "serverchan"}) == "通知未启用。"
        send.assert_not_called()


def test_no_candidates_does_not_send(monkeypatch):
    monkeypatch.setenv("SERVERCHAN_SENDKEY", "SCT-test")
    with patch("vegas_signal_system.notifications.send_serverchan") as send:
        result = notify_observations(
            [{"symbol_id": "NVDA", "status": "WATCH_ENTRY_CONDITIONS"}],
            {"enabled": True, "provider": "serverchan"},
        )
        assert "没有 EMA144 触碰观察候选" in result
        send.assert_not_called()


def test_candidate_sends_notification(monkeypatch):
    monkeypatch.setenv("SERVERCHAN_SENDKEY", "SCT-test")
    candidate = {
        "symbol_id": "NVDA", "symbol_name": "英伟达",
        "status": "WATCH_ENTRY_CONFIRMATION", "direction_4h": "up",
        "direction_8h": "up", "entry_timeframe": "1h", "close": 150.0,
        "timestamp": "2026-10-20T10:00:00+00:00", "message": "触碰EMA144",
    }
    with patch("vegas_signal_system.notifications.send_serverchan") as send:
        result = notify_observations([candidate], {"enabled": True, "provider": "serverchan"})
        assert "1 条" in result
        assert "英伟达" in send.call_args.args[2]


def test_test_notification_sends_test_message(monkeypatch):
    monkeypatch.setenv("SERVERCHAN_SENDKEY", "SCT-test")
    with patch("vegas_signal_system.notifications.send_serverchan") as send:
        result = send_test_notification({"enabled": True, "provider": "serverchan"})
        assert "已成功提交" in result
        assert "不代表存在交易信号" in send.call_args.args[2]


def test_missing_secret_is_reported(monkeypatch):
    monkeypatch.delenv("SERVERCHAN_SENDKEY", raising=False)
    assert "SERVERCHAN_SENDKEY" in send_test_notification(
        {"enabled": True, "provider": "serverchan"}
    )


def test_serverchan_turbo_endpoint_and_success():
    from unittest.mock import MagicMock
    from vegas_signal_system.notifications import send_serverchan

    response = MagicMock()
    response.read.return_value = b'{"code":0,"message":"ok"}'
    response.__enter__.return_value = response
    with patch("vegas_signal_system.notifications.urllib.request.urlopen", return_value=response) as urlopen:
        assert send_serverchan("SCT-secret", "Test", "Body")["code"] == 0
        assert "https://sctapi.ftqq.com/SCT-secret.send" in urlopen.call_args.args[0].full_url


def test_serverchan_sc3_endpoint():
    from unittest.mock import MagicMock
    from vegas_signal_system.notifications import send_serverchan

    response = MagicMock()
    response.read.return_value = b'{"code":0,"message":"ok"}'
    response.__enter__.return_value = response
    with patch("vegas_signal_system.notifications.urllib.request.urlopen", return_value=response) as urlopen:
        send_serverchan("sctp123t-secret", "Test", "Body")
        assert "https://123.push.ft07.com/send/sctp123t-secret.send" in urlopen.call_args.args[0].full_url
