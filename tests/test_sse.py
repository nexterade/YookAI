import io
import json
import unittest

from app.sse import SSEStreamer, format_sse, normalize_chunk


class SSETests(unittest.TestCase):
    def test_format_sse_json_event(self):
        self.assertEqual(format_sse({"type": "done"}), 'data: {"type": "done"}\n\n')

    def test_normalize_reasoning(self):
        self.assertEqual(normalize_chunk({"type": "reasoning", "content": "think"}), {"type": "reasoning", "content": "think"})

    def test_normalize_content(self):
        self.assertEqual(normalize_chunk({"type": "content", "content": "answer"}), {"type": "content", "content": "answer"})

    def test_normalize_done(self):
        self.assertEqual(normalize_chunk({"type": "done"}), {"type": "done"})

    def test_normalize_error(self):
        self.assertEqual(normalize_chunk({"type": "error", "message": "boom"}), {"type": "error", "message": "boom"})

    def test_normalize_openai_delta_content(self):
        self.assertEqual(normalize_chunk({"choices": [{"delta": {"content": "hi"}}]}), {"type": "content", "content": "hi"})

    def test_streamer_send_event(self):
        target = io.BytesIO()
        stream = SSEStreamer(target)
        stream.send_event({"type": "content", "content": "x"})
        self.assertEqual(target.getvalue(), b'data: {"type": "content", "content": "x"}\n\n')

    def test_streamer_raw_and_close(self):
        target = io.BytesIO()
        stream = SSEStreamer(target)
        stream.send_raw(": keep-alive\n")
        self.assertIn(b": keep-alive", target.getvalue())
        stream.close()


if __name__ == "__main__":
    unittest.main()

class SSERegressionTests(unittest.TestCase):
    def test_close_does_not_close_http_owned_stream(self):
        target = io.BytesIO()
        stream = SSEStreamer(target)
        stream.close()
        target.write(b'owned-by-handler')
        self.assertEqual(target.getvalue(), b'owned-by-handler')
