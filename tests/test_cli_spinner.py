import io
import os
import sys
import time
import unittest
from unittest.mock import patch

from tools.configure import _Spinner


class _TTY(io.StringIO):
    def isatty(self):
        return True


class SpinnerTests(unittest.TestCase):
    def test_interactive_spinner_advances_frames_and_clears(self):
        output = _TTY()
        with patch('tools.configure.sys.stdout', output), patch.dict(os.environ, {'TERM': 'xterm'}):
            with _Spinner('Working', interval=0.01):
                time.sleep(0.055)
        rendered = output.getvalue()
        self.assertIn('⠋ Working', rendered)
        self.assertGreaterEqual(sum(frame in rendered for frame in _Spinner.FRAMES), 2)
        self.assertTrue(rendered.endswith('\r\033[2K'))

    def test_non_tty_prints_static_status_without_escape_sequences(self):
        output = io.StringIO()
        with patch('tools.configure.sys.stdout', output), patch.dict(os.environ, {'TERM': 'dumb'}):
            with _Spinner('Checking'):
                time.sleep(0.02)
        self.assertEqual(output.getvalue(), 'Checking\n')


if __name__ == '__main__':
    unittest.main()
