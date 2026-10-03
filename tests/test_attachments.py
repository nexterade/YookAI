import tempfile
import unittest
from pathlib import Path

from core.attachments import AttachmentStore


class AttachmentStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = AttachmentStore(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_save_and_read_text(self):
        meta = self.store.save("../../notes.txt", "text/plain", b"hello attachment")
        self.assertEqual(meta["name"], "notes.txt")
        self.assertEqual(self.store.read_text(meta["id"]), "hello attachment")
        self.assertEqual(self.store.get(meta["id"])["size"], len(b"hello attachment"))

    def test_rejects_large_upload(self):
        with self.assertRaises(ValueError):
            self.store.save("big.bin", "application/octet-stream", b"x" * (20 * 1024 * 1024 + 1))

    def test_delete(self):
        meta = self.store.save("x.txt", "text/plain", b"x")
        self.assertTrue(self.store.delete(meta["id"]))
        self.assertFalse(self.store.delete(meta["id"]))


if __name__ == "__main__":
    unittest.main()
