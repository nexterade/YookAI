import json
import concurrent.futures
import tempfile
import time
import unittest
from pathlib import Path

from app.session import SessionManager


class SessionManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.manager = SessionManager(Path(self.temp.name))

    def tearDown(self):
        self.temp.cleanup()

    def test_concurrent_create_ids_are_unique(self):
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            sessions = list(pool.map(lambda _: self.manager.create_session(), range(20)))
        ids = [item["id"] for item in sessions]
        self.assertEqual(len(ids), len(set(ids)))

    def test_concurrent_save_uses_independent_temp_files(self):
        session = self.manager.create_session()
        def save(i):
            copy = dict(session)
            copy["messages"] = [{"role": "user", "content": str(i)}]
            self.manager.save_session(copy)
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(save, range(20)))
        loaded = self.manager.load_session(session["id"])
        self.assertEqual(len(loaded["messages"]), 1)

    def test_create_session_creates_file(self):
        session = self.manager.create_session("New Chat", "openrouter", "model-x")
        self.assertRegex(session["id"], r"^\d{4}-\d{2}-\d{2}-\d{3}$")
        self.assertTrue(self.manager.get_session_path(session["id"]).exists())

    def test_save_load_roundtrip(self):
        session = self.manager.create_session()
        session["metadata"]["test"] = True
        self.manager.save_session(session)
        loaded = self.manager.load_session(session["id"])
        self.assertTrue(loaded["metadata"]["test"])
        self.assertEqual(loaded["id"], session["id"])

    def test_list_sessions_sorted_by_updated_at(self):
        first = self.manager.create_session("First")
        time.sleep(0.002)
        second = self.manager.create_session("Second")
        listed = self.manager.list_sessions()
        self.assertEqual([item["id"] for item in listed[:2]], [second["id"], first["id"]])

    def test_delete_session(self):
        session = self.manager.create_session()
        self.assertTrue(self.manager.delete_session(session["id"]))
        self.assertFalse(self.manager.get_session_path(session["id"]).exists())
        self.assertFalse(self.manager.delete_session(session["id"]))

    def test_add_message(self):
        session = self.manager.create_session()
        message = self.manager.add_message(session["id"], "user", "Hello YookAI", source="test")
        loaded = self.manager.load_session(session["id"])
        self.assertEqual(message["role"], "user")
        self.assertEqual(loaded["messages"][0]["content"], "Hello YookAI")
        self.assertEqual(loaded["messages"][0]["source"], "test")
        self.assertEqual(loaded["title"], "Hello YookAI")

    def test_invalid_id_and_missing_session(self):
        with self.assertRaises(ValueError):
            self.manager.get_session_path("../escape")
        with self.assertRaises(FileNotFoundError):
            self.manager.load_session("2026-10-01-999")

    def test_corrupt_json(self):
        path = self.manager.get_session_path("2026-10-01-001")
        path.write_text("{not-json", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.manager.load_session("2026-10-01-001")


if __name__ == "__main__":
    unittest.main()
