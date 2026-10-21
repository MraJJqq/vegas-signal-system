import json
import os
import unittest
from unittest.mock import patch
from urllib.error import URLError

from notification_digest_v5 import send_serverchan


class ServerChanTests(unittest.TestCase):
    def test_missing_key_fails_before_network(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "SERVERCHAN_SENDKEY"):
                send_serverchan("test")

    def test_non_turbo_key_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "starting with SCT"):
            send_serverchan("test", sendkey="not-a-key")

    def test_success_response_is_accepted(self):
        class FakeResponse:
            status = 200
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self):
                return json.dumps({"code": 0, "message": "成功"}).encode()

        with patch("notification_digest_v5.urlopen", return_value=FakeResponse()) as mocked:
            send_serverchan("微信推送测试", sendkey="SCT_test_key")
        request = mocked.call_args.args[0]
        self.assertIn("sctapi.ftqq.com/SCT_test_key.send", request.full_url)
        self.assertEqual(request.method, "POST")

    def test_api_rejection_is_reported(self):
        class FakeResponse:
            status = 200
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self):
                return json.dumps({"code": 40001, "message": "bad key"}).encode()

        with patch("notification_digest_v5.urlopen", return_value=FakeResponse()):
            with self.assertRaisesRegex(RuntimeError, "推送失败"):
                send_serverchan("test", sendkey="SCT_test_key")


if __name__ == "__main__":
    unittest.main()
