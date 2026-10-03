import tempfile
import unittest
from pathlib import Path

from core.tools.engine import ToolEngine
from core.tools.builtins import ToolExecutionError


class Beta2ToolTests(unittest.TestCase):
    def config(self, shell=False):
        return {"tools": {"enabled": True, "shell": {"enabled": shell, "timeout": 2}}}

    def test_calculator_is_safe(self):
        engine = ToolEngine(self.config())
        result = engine.execute("calculator", {"expression": "2 + 3 * 4"})
        self.assertEqual(result["result"], "14")
        with self.assertRaises(ToolExecutionError):
            engine.execute("calculator", {"expression": "__import__('os').system('id')"})

    def test_filesystem_is_workspace_scoped(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = ToolEngine(self.config(), Path(tmp) / "workspace")
            (Path(tmp) / "workspace" / "hello.txt").write_text("hello", encoding="utf-8")
            self.assertEqual(engine.execute("filesystem.read", {"path": "hello.txt"})["result"], "hello")
            with self.assertRaises(ToolExecutionError):
                engine.execute("filesystem.read", {"path": "../outside.txt"})

    def test_shell_requires_enablement_and_confirmation(self):
        disabled = ToolEngine(self.config(False))
        self.assertNotIn("shell", {item["name"] for item in disabled.list_tools()})
        engine = ToolEngine(self.config(True))
        first = engine.execute("shell", {"command": "pwd"})
        self.assertEqual(first["status"], "confirmation_required")
        second = engine.execute("shell", {"command": "pwd"}, first["confirmation_token"])
        self.assertEqual(second["status"], "ok")
        bad = engine.execute("shell", {"command": "ls /"})
        with self.assertRaises(ToolExecutionError):
            engine.execute("shell", {"command": "ls /"}, bad["confirmation_token"])


if __name__ == "__main__":
    unittest.main()
