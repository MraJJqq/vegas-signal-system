import json, os, sys, tempfile, unittest
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "v9"))
import ntfy_notifier

CORE = ["BTC", "HYPE", "XAU", "CL"]
STOCKS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "INTC", "QCOM", "AMD", "TSM", "AVGO", "ORCL", "ARM", "MU", "ASML", "SNDK", "SKHYNIX", "MRVL", "GLW", "HOOD", "CBRS", "SPCX"]


class BarkNotifierTests(unittest.TestCase):
    def test_empty_report_has_both_no_change_groups(self):
        body, symbols = ntfy_notifier.build_body({"signals": []})
        self.assertEqual(symbols, [])
        self.assertEqual(body, "🔸 美股巨头\n▰ No change ▰\n\n🔸 核心能源\n▰ No change ▰")

    def test_formal_signals_deduplicated_and_non_formal_ignored(self):
        body, symbols = ntfy_notifier.build_body({"signals": [
            {"formal_signal": True, "symbol": "NVDAUSDT"},
            {"formal_signal": True, "symbol": "BTCUSDT"},
            {"formal_signal": True, "symbol": "NVDAUSDT"},
            {"formal_signal": False, "symbol": "TSLAUSDT"}]})
        self.assertEqual(symbols, ["NVDA", "BTC"])
        self.assertNotIn("▰ TSLA ▰", body)

    def test_only_fixed_pool_symbols_are_rendered(self):
        _, symbols = ntfy_notifier.build_body(
            {"signals": [{"formal_signal": True, "symbol": f"{s}USDT"} for s in CORE + STOCKS]
             + [{"formal_signal": True, "symbol": "JPMUSDT"}]})
        self.assertEqual(set(symbols), set(CORE + STOCKS))
        self.assertEqual(len(symbols), 27)

    def test_public_signal_state_matches_bark_symbol_list(self):
        report = {"finished_at_utc": "2026-10-29T12:00:00+00:00", "signals": [
            {"formal_signal": True, "symbol": "NVDAUSDT"},
            {"formal_signal": True, "symbol": "BTCUSDT"},
            {"formal_signal": True, "symbol": "NVDAUSDT"},
            {"formal_signal": False, "symbol": "TSLAUSDT"},
            {"formal_signal": True, "symbol": "JPMUSDT"},
        ]}
        state = ntfy_notifier.build_public_signal_state(report)
        signals = state["__daily_formal_signals__"]["signals"]
        self.assertEqual(state["__daily_formal_signals__"]["date"], "2026-10-29")
        self.assertEqual([item["symbol"] for item in signals], ["NVDAUSDT", "BTCUSDT"])
        self.assertTrue(all(item["formal_signal"] is True for item in signals))

    def test_payload_has_no_title_or_url_and_posts_once(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "report.json"
            path.write_text(json.dumps({"signals": []}), encoding="utf-8")
            with patch.dict(os.environ, {"V9_BARK_KEY": "test-key", "V9_BARK_STATE_PATH": str(Path(d) / "state.json")}, clear=False), \
                 patch.object(ntfy_notifier.urllib.request, "urlopen") as urlopen:
                response = urlopen.return_value.__enter__.return_value
                response.status = 200
                response.read.return_value = b'{"code":200}'
                self.assertEqual(ntfy_notifier.send_notification(str(path)), 0)
                payload = json.loads(urlopen.call_args.args[0].data.decode())
                self.assertNotIn("title", payload)
                self.assertNotIn("url", payload)
                self.assertEqual(payload["device_key"], "test-key")
                self.assertEqual(urlopen.call_args.kwargs["timeout"], 20)

    def test_public_signal_manifest_is_written_even_when_bark_fails(self):
        with tempfile.TemporaryDirectory() as d:
            report_path = Path(d) / "report.json"
            public_path = Path(d) / "public.json"
            report_path.write_text(json.dumps({
                "finished_at_utc": "2026-10-30T02:00:00+00:00",
                "signals": [{"formal_signal": True, "symbol": "NVDAUSDT"}],
            }), encoding="utf-8")
            env = {
                "V9_BARK_KEY": "test-key",
                "V9_BARK_STATE_PATH": str(Path(d) / "state.json"),
                "V9_PUBLIC_SIGNAL_PATH": str(public_path),
            }
            with patch.dict(os.environ, env, clear=False), \
                 patch.object(ntfy_notifier.urllib.request, "urlopen", side_effect=urllib.error.URLError("offline")), \
                 patch.object(ntfy_notifier.time, "sleep"):
                self.assertEqual(ntfy_notifier.send_notification(str(report_path)), 1)
            state = json.loads(public_path.read_text(encoding="utf-8"))
            self.assertEqual(
                state["__daily_formal_signals__"]["signals"][0]["symbol"],
                "NVDAUSDT",
            )

    def test_pending_notification_is_retried_before_newer_scan_content(self):
        with tempfile.TemporaryDirectory() as d:
            report_path = Path(d) / "report.json"
            state_path = Path(d) / "state.json"
            pending_path = Path(d) / "pending.json"
            old_report = {
                "finished_at_utc": "2026-10-30T02:00:00+00:00",
                "signals": [{"formal_signal": True, "symbol": "NVDAUSDT"}],
            }
            new_report = {
                "finished_at_utc": "2026-10-30T03:00:00+00:00",
                "signals": [{"formal_signal": True, "symbol": "AMDUSDT"}],
            }
            old_body, old_symbols = ntfy_notifier.build_body(old_report)
            old_fingerprint = ntfy_notifier.notification_fingerprint(old_body, old_report)
            ntfy_notifier.save_pending_notification(
                str(pending_path), old_fingerprint, old_body, old_report, old_symbols
            )
            report_path.write_text(json.dumps(new_report), encoding="utf-8")
            env = {
                "V9_BARK_KEY": "test-key",
                "V9_BARK_STATE_PATH": str(state_path),
                "V9_BARK_PENDING_PATH": str(pending_path),
            }
            with patch.dict(os.environ, env, clear=False), \
                 patch.object(ntfy_notifier.urllib.request, "urlopen") as urlopen:
                response = urlopen.return_value.__enter__.return_value
                response.status = 200
                response.read.return_value = b'{"code":200}'
                self.assertEqual(ntfy_notifier.send_notification(str(report_path)), 0)
                self.assertEqual(urlopen.call_count, 2)
                first_payload = json.loads(urlopen.call_args_list[0].args[0].data.decode())
                second_payload = json.loads(urlopen.call_args_list[1].args[0].data.decode())
                self.assertIn("NVDA", first_payload["body"])
                self.assertIn("AMD", second_payload["body"])
            self.assertIsNone(json.loads(pending_path.read_text(encoding="utf-8"))["pending"])
            accepted = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(accepted["fingerprint"],
                             ntfy_notifier.notification_fingerprint(
                                 ntfy_notifier.build_body(new_report)[0], new_report
                             ))

    def test_retries_transient_network_failure_then_succeeds(self):
        with patch.object(ntfy_notifier.urllib.request, "urlopen") as urlopen, \
             patch.object(ntfy_notifier.time, "sleep") as sleep:
            response = urlopen.return_value.__enter__.return_value
            response.status = 200
            response.read.return_value = b'{"code":200}'
            urlopen.side_effect = [urllib.error.URLError("temporary"), urlopen.return_value]
            ntfy_notifier.post_bark({"device_key": "test-key", "body": "test"})
            self.assertEqual(urlopen.call_count, 2)
            sleep.assert_called_once_with(1)

    def test_retries_server_error_but_stops_after_three_attempts(self):
        error = urllib.error.HTTPError(
            ntfy_notifier.BARK_ENDPOINT, 503, "Unavailable", {}, None
        )
        with patch.object(ntfy_notifier.urllib.request, "urlopen", side_effect=error) as urlopen, \
             patch.object(ntfy_notifier.time, "sleep") as sleep:
            with self.assertRaisesRegex(RuntimeError, "Bark HTTP 503"):
                ntfy_notifier.post_bark({"device_key": "test-key", "body": "test"})
            self.assertEqual(urlopen.call_count, 3)
            self.assertEqual([call.args[0] for call in sleep.call_args_list], [1, 2])

    def test_rate_limit_retry_honors_retry_after_header(self):
        error = urllib.error.HTTPError(
            ntfy_notifier.BARK_ENDPOINT, 429, "Too Many Requests",
            {"Retry-After": "4"}, None
        )
        success_response = MagicMock()
        success_response.__enter__.return_value.status = 200
        success_response.__enter__.return_value.read.return_value = b'{"code":200}'
        with patch.object(ntfy_notifier.urllib.request, "urlopen", side_effect=[error, success_response]), \
             patch.object(ntfy_notifier.time, "sleep") as sleep:
            ntfy_notifier.post_bark({"device_key": "test-key", "body": "test"})
            sleep.assert_called_once_with(4.0)

    def test_retry_after_is_bounded(self):
        self.assertEqual(ntfy_notifier._retry_delay(1, "999"), 60.0)
        self.assertEqual(ntfy_notifier._retry_delay(2, "invalid"), 2.0)

    def test_rejects_bark_application_error(self):
        with patch.object(ntfy_notifier.urllib.request, "urlopen") as urlopen:
            response = urlopen.return_value.__enter__.return_value
            response.status = 200
            response.read.return_value = b'{"code":400,"message":"bad request"}'
            with self.assertRaisesRegex(RuntimeError, "code=400"):
                ntfy_notifier.post_bark({"device_key": "test-key", "body": "test"})

    def test_oil_symbol_alias(self):
        self.assertEqual(ntfy_notifier.display_symbol("CLUSDT"), "CL")

    def test_identical_notification_is_sent_on_every_scan(self):
        with tempfile.TemporaryDirectory() as d:
            report_path = Path(d) / "report.json"
            state_path = Path(d) / "state.json"
            report = {"finished_at_utc": "2026-10-30T02:00:00+00:00", "signals": [
                {"formal_signal": True, "symbol": "NVDAUSDT"}
            ]}
            report_path.write_text(json.dumps(report), encoding="utf-8")
            env = {"V9_BARK_KEY": "test-key", "V9_BARK_STATE_PATH": str(state_path)}
            with patch.dict(os.environ, env, clear=False), \
                 patch.object(ntfy_notifier.urllib.request, "urlopen") as urlopen:
                response = urlopen.return_value.__enter__.return_value
                response.status = 200
                response.read.return_value = b'{"code":200}'
                self.assertEqual(ntfy_notifier.send_notification(str(report_path)), 0)
                self.assertEqual(ntfy_notifier.send_notification(str(report_path)), 0)
                self.assertEqual(urlopen.call_count, 2)

    def test_changed_notification_is_sent_after_previous_content(self):
        with tempfile.TemporaryDirectory() as d:
            report_path = Path(d) / "report.json"
            state_path = Path(d) / "state.json"
            env = {"V9_BARK_KEY": "test-key", "V9_BARK_STATE_PATH": str(state_path)}
            with patch.dict(os.environ, env, clear=False), \
                 patch.object(ntfy_notifier.urllib.request, "urlopen") as urlopen:
                response = urlopen.return_value.__enter__.return_value
                response.status = 200
                response.read.return_value = b'{"code":200}'
                for symbol in ("NVDAUSDT", "AMDUSDT"):
                    report_path.write_text(json.dumps({
                        "finished_at_utc": "2026-10-30T02:00:00+00:00",
                        "signals": [{"formal_signal": True, "symbol": symbol}],
                    }), encoding="utf-8")
                    self.assertEqual(ntfy_notifier.send_notification(str(report_path)), 0)
                self.assertEqual(urlopen.call_count, 2)

    def test_same_content_on_new_beijing_day_is_sent_again(self):
        with tempfile.TemporaryDirectory() as d:
            report_path = Path(d) / "report.json"
            state_path = Path(d) / "state.json"
            env = {"V9_BARK_KEY": "test-key", "V9_BARK_STATE_PATH": str(state_path)}
            with patch.dict(os.environ, env, clear=False), \
                 patch.object(ntfy_notifier.urllib.request, "urlopen") as urlopen:
                response = urlopen.return_value.__enter__.return_value
                response.status = 200
                response.read.return_value = b'{"code":200}'
                for timestamp in ("2026-10-30T02:00:00+00:00", "2026-10-31T02:00:00+00:00"):
                    report_path.write_text(json.dumps({
                        "finished_at_utc": timestamp,
                        "signals": [{"formal_signal": True, "symbol": "NVDAUSDT"}],
                    }), encoding="utf-8")
                    self.assertEqual(ntfy_notifier.send_notification(str(report_path)), 0)
                self.assertEqual(urlopen.call_count, 2)


    def test_standalone_pending_retry_sends_and_clears_queue(self):
        with tempfile.TemporaryDirectory() as d:
            state_path = Path(d) / "state.json"
            pending_path = Path(d) / "pending.json"
            today = ntfy_notifier.datetime.now(
                ntfy_notifier.timezone(ntfy_notifier.timedelta(hours=8))
            ).date().isoformat()
            pending = {
                "version": 1,
                "date": today,
                "fingerprint": "pending-fingerprint",
                "body": "🔸 美股巨头\n▰ NVDA ▰",
                "symbols": ["NVDA"],
            }
            pending_path.write_text(json.dumps(pending), encoding="utf-8")
            env = {
                "V9_BARK_KEY": "test-key",
                "V9_BARK_STATE_PATH": str(state_path),
                "V9_BARK_PENDING_PATH": str(pending_path),
            }
            with patch.dict(os.environ, env, clear=False), \
                 patch.object(ntfy_notifier.urllib.request, "urlopen") as urlopen:
                response = urlopen.return_value.__enter__.return_value
                response.status = 200
                response.read.return_value = b'{"code":200}'
                self.assertEqual(ntfy_notifier.retry_pending_notification(), 0)
                payload = json.loads(urlopen.call_args.args[0].data.decode())
                self.assertEqual(payload["body"], pending["body"])
            self.assertIsNone(json.loads(pending_path.read_text())["pending"])
            self.assertEqual(json.loads(state_path.read_text())["fingerprint"], "pending-fingerprint")

    def test_standalone_pending_retry_preserves_queue_on_delivery_failure(self):
        with tempfile.TemporaryDirectory() as d:
            state_path = Path(d) / "state.json"
            pending_path = Path(d) / "pending.json"
            today = ntfy_notifier.datetime.now(
                ntfy_notifier.timezone(ntfy_notifier.timedelta(hours=8))
            ).date().isoformat()
            pending = {
                "version": 1,
                "date": today,
                "fingerprint": "pending-fingerprint",
                "body": "pending alert",
                "symbols": ["NVDA"],
            }
            pending_path.write_text(json.dumps(pending), encoding="utf-8")
            env = {
                "V9_BARK_KEY": "test-key",
                "V9_BARK_STATE_PATH": str(state_path),
                "V9_BARK_PENDING_PATH": str(pending_path),
            }
            with patch.dict(os.environ, env, clear=False), \
                 patch.object(ntfy_notifier.urllib.request, "urlopen",
                              side_effect=urllib.error.URLError("offline")), \
                 patch.object(ntfy_notifier.time, "sleep"):
                self.assertEqual(ntfy_notifier.retry_pending_notification(), 1)
            self.assertEqual(json.loads(pending_path.read_text())["fingerprint"], "pending-fingerprint")
            self.assertFalse(state_path.exists())


if __name__ == "__main__":
    unittest.main()
