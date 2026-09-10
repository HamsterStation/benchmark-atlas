import io
import json
import unittest
from unittest.mock import patch, MagicMock

from collector.collect import read_chat_stream, ModelClient


def chunk(content=None, reason=None, **delta):
    return ('data: ' + json.dumps({"choices": [{"index": 0, "delta": {"content": content, **delta}, "finish_reason": reason}]}, ensure_ascii=False) + '\n\n').encode()


class ModelStreamTests(unittest.TestCase):
    def test_unicode_fragmented_json_is_assembled_without_execution(self):
        raw = b': keepalive\n\n' + chunk('{"summaryZh":"') + chunk('测试资料，不可发布') + chunk('"}') + chunk(reason="stop") + b'data: [DONE]\n\n'
        self.assertEqual(read_chat_stream(io.BytesIO(raw), 10000, 10), {"summaryZh": "测试资料，不可发布"})

    def test_truncation_errors_and_tool_calls_are_rejected(self):
        for raw in [chunk('{}'), chunk('{}', reason="length") + b'data: [DONE]\n\n',
                    chunk('{}') + b'data: [DONE]\n\n', b'data: {"error": {"message": "untrusted"}}\n\n',
                    chunk(tool_calls=[{"function": {"name": "do_not_execute"}}])]:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                read_chat_stream(io.BytesIO(raw), 10000, 10)

    def test_response_budget_and_deadline_are_enforced(self):
        with self.assertRaises(ValueError):
            read_chat_stream(io.BytesIO(chunk('x' * 100)), 50, 10)
        with self.assertRaises(TimeoutError):
            read_chat_stream(io.BytesIO(chunk('{}')), 10000, -1)

    def test_provider_credential_echo_is_rejected_before_persistence(self):
        with patch.dict('os.environ', {"MODEL_API_KEY": "TEST-ONLY-CREDENTIAL", "MODEL_API_URL": "https://example.invalid/chat", "MODEL_NAME": "test", "MODEL_API_STREAM": "false"}):
            client = ModelClient({"model_timeout_seconds": 10, "model_max_output_bytes": 10000})
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({"choices": [{"message": {"content": '{"summaryZh":"TEST-ONLY-CREDENTIAL"}'}}]}).encode()
        with patch('collector.collect.build_opener') as opener:
            opener.return_value.open.return_value = response
            with self.assertRaisesRegex(ValueError, "credential"):
                client.generate("test", {key: {} for key in ["roles", "targets", "scenarios", "capabilities"]})
