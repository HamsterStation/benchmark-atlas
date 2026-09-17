import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from collector.collect import ModelClient, ModelResponseFormatError, parse_model_json, read_responses_stream, responses_output, safe_model_http_error


def completed(text='{"summaryZh":"仅测试，不可发布"}'):
    return {"status": "completed", "error": None, "incomplete_details": None,
            "output": [{"type": "reasoning", "summary": [{"text": "not paper content"}]},
                       {"type": "message", "role": "assistant", "status": "completed",
                        "content": [{"type": "output_text", "text": text}]}]}


def event(kind, **data):
    return (f'event: {kind}\r\ndata: ' + json.dumps({"type": kind, **data}, ensure_ascii=False) + '\r\n\r\n').encode()


class ResponsesTests(unittest.TestCase):
    def test_only_one_json_fence_is_tolerated_and_extra_prose_is_rejected(self):
        self.assertEqual(parse_model_json('```json\n{"summaryZh":"仅供测试"}\n```'), {"summaryZh": "仅供测试"})
        for text in ['说明：{"summaryZh":"仅供测试"}', '```python\nprint("do not execute")\n```',
                     '```json\n{}\n```\nmore text', '{"summaryZh":"bad \\u123"}']:
            with self.subTest(text=text), self.assertRaises(ModelResponseFormatError) as error:
                parse_model_json(text)
            self.assertEqual(error.exception.stage, 'assistant_json')

    def test_provider_message_is_reduced_to_allowlisted_parameter_hints(self):
        body = {"error": {"code": "invalid_request_error", "param": "text.format",
                          "message": "Unsupported parameter: text.format SECRET-DO-NOT-PRINT"}}
        error = HTTPError('https://example.invalid/SECRET', 400, 'SECRET', {}, io.BytesIO(json.dumps(body).encode()))
        self.assertEqual(safe_model_http_error(error), {"http_status": 400, "provider_code": "invalid_request_error",
                                                     "parameter_names": ["text.format"], "parameter_issue": "unsupported"})
        for body in ['Unsupported parameter: max_output_tokens SECRET',
                     '{"error":"Unsupported parameter: max_output_tokens SECRET"}']:
            error = HTTPError('https://example.invalid', 400, 'SECRET', {}, io.BytesIO(body.encode()))
            self.assertEqual(safe_model_http_error(error), {"http_status": 400,
                             "parameter_names": ["max_output_tokens"], "parameter_issue": "unsupported"})

    def test_completed_envelope_parses_unicode_without_using_reasoning_or_partial_deltas(self):
        raw = b': keepalive\n\n' + event('response.output_text.delta', delta='incomplete fragment')
        raw += event('response.completed', response=completed())
        self.assertEqual(read_responses_stream(io.BytesIO(raw), 10000, 10), {"summaryZh": "仅测试，不可发布"})

    def test_relay_can_omit_repeated_output_only_after_successful_completion(self):
        text = '{"summaryZh":"仅测试，不可发布"}'
        deltas = event('response.output_text.delta', delta=text[:12], output_index=1, content_index=0)
        deltas += event('response.output_text.delta', delta=text[12:], output_index=1, content_index=0)
        deltas += event('response.output_text.done', text=text, output_index=1, content_index=0)
        raw = deltas + event('response.completed', response={"status":"completed", "output":[]})
        self.assertEqual(read_responses_stream(io.BytesIO(raw), 10000, 10), {"summaryZh":"仅测试，不可发布"})
        for ending in [b'', event('response.incomplete'), event('response.failed'),
                       event('response.completed', response={"status":"incomplete", "output":[]}),
                       event('response.function_call_arguments.delta', delta='{}'),
                       event('response.content_part.done', part={"type":"refusal"})]:
            with self.subTest(ending=ending), self.assertRaises(ValueError):
                read_responses_stream(io.BytesIO(deltas + ending), 10000, 10)

    def test_failure_refusal_tool_output_and_missing_completion_are_rejected(self):
        cases = [event('response.output_text.delta', delta='{}'), b'data: [DONE]\n\n',
                 event('response.failed'), event('response.incomplete'), event('error'),
                 event('response.refusal.delta', delta='refused'),
                 event('response.output_item.added', item={"type": "function_call", "name": "do_not_execute"})]
        for status in ['incomplete', 'failed', 'in_progress']:
            cases.append(event('response.completed', response={**completed(), "status": status}))
        for output in [[{"type": "function_call"}], [],
                       [{"type": "message", "role": "assistant", "status": "completed", "content": [{"type": "refusal"}]}]]:
            cases.append(event('response.completed', response={**completed(), "output": output}))
        for raw in cases:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                read_responses_stream(io.BytesIO(raw), 10000, 10)

    def test_response_budget_deadline_and_provider_errors_fail_closed(self):
        raw = event('response.completed', response=completed())
        with self.assertRaises(ValueError):
            read_responses_stream(io.BytesIO(raw), 50, 10)
        with self.assertRaises(TimeoutError):
            read_responses_stream(io.BytesIO(raw), 10000, -1)
        for field in ['error', 'incomplete_details']:
            response = completed(); response[field] = {"message": "unsafe text"}
            with self.subTest(field=field), self.assertRaises(ValueError):
                responses_output(response)

    def test_post_payload_and_stream_or_nonstream_output_use_responses_protocol(self):
        taxonomy = {key: {} for key in ['roles', 'targets', 'scenarios', 'capabilities']}
        for stream in [True, False]:
            with self.subTest(stream=stream), patch.dict('os.environ', {
                'MODEL_API_KEY': 'TEST-ONLY-CREDENTIAL', 'MODEL_API_URL': 'https://example.invalid/openai/v1/responses',
                'MODEL_NAME': 'gpt-5.6-luna', 'MODEL_API_STREAM': str(stream).lower()
            }):
                client = ModelClient({"model_timeout_seconds": 10, "model_max_output_bytes": 10000})
                raw = event('response.completed', response=completed()) if stream else json.dumps(completed()).encode()
                with patch('collector.collect.build_opener') as opener:
                    opener.return_value.open.return_value = io.BytesIO(raw)
                    result = client.generate('UNTRUSTED MATERIAL', taxonomy)
                    request = opener.return_value.open.call_args.args[0]
                    payload = json.loads(request.data)
                self.assertEqual(result, {"summaryZh": "仅测试，不可发布"})
                self.assertEqual(request.get_method(), 'POST')
                self.assertEqual(payload['model'], 'gpt-5.6-luna')
                self.assertEqual(payload['input'][0]['role'], 'developer')
                self.assertEqual(payload['input'][0]['content'][0]['text'], payload['instructions'])
                self.assertEqual(payload['input'][1]['role'], 'user')
                self.assertEqual(payload['input'][1]['content'][0]['text'], 'UNTRUSTED MATERIAL')
                self.assertNotIn('UNTRUSTED MATERIAL', payload['instructions'])
                # Simulate a relay replacing its top-level persona: app rules survive.
                payload['instructions'] = 'Provider default persona'
                self.assertIn('summaryZh', payload['input'][0]['content'][0]['text'])
                self.assertNotIn('text', payload)
                self.assertNotIn('max_output_tokens', payload)
                self.assertFalse(payload['store'])
                self.assertEqual(payload['tools'], [])
                self.assertEqual(payload.get('stream', False), stream)
                for chat_field in ['messages', 'response_format', 'max_tokens', 'temperature']:
                    self.assertNotIn(chat_field, payload)

    def test_responses_credential_echo_and_corrupt_unicode_are_rejected(self):
        with patch.dict('os.environ', {'MODEL_API_KEY': 'TEST-ONLY-CREDENTIAL',
                        'MODEL_API_URL': 'https://example.invalid/v1/responses', 'MODEL_NAME': 'test', 'MODEL_API_STREAM': 'true'}):
            client = ModelClient({"model_timeout_seconds": 10, "model_max_output_bytes": 10000})
        for text in ['{"summaryZh":"TEST-ONLY-CREDENTIAL"}', '{"summaryZh":"bad \ufffd"}']:
            with patch('collector.collect.build_opener') as opener, self.assertRaises(ValueError):
                opener.return_value.open.return_value = io.BytesIO(event('response.completed', response=completed(text)))
                client.generate('material', {key: {} for key in ['roles', 'targets', 'scenarios', 'capabilities']})
