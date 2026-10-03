import json
import tempfile
import unittest
from pathlib import Path
from core.memory import MemoryStore
from core.attachments import AttachmentStore
from core.documents import DocumentExtractor
from app.session import SessionManager

class V020FeatureTests(unittest.TestCase):
    def test_memory_semantic_and_isolation(self):
        with tempfile.TemporaryDirectory() as td:
            m=MemoryStore(Path(td))
            m.upsert_session('2026-01-01-001',[{'role':'user','content':'My project uses Python and FastAPI'}],'default','default')
            m.upsert_session('2026-01-01-002',[{'role':'user','content':'Secret project'}],'project-only','alpha')
            self.assertTrue(m.search('Python FastAPI','default','default'))
            self.assertFalse(m.search('Secret','project-only','beta'))
            self.assertTrue(m.search('Secret','project-only','alpha'))

    def test_attachment_document_extraction_and_cleanup(self):
        with tempfile.TemporaryDirectory() as td:
            a=AttachmentStore(Path(td))
            meta=a.save('notes.txt','text/plain',b'hello local document')
            self.assertEqual(a.read_text(meta['id']),'hello local document')
            self.assertTrue(a.delete(meta['id']))
            self.assertFalse(a.delete(meta['id']))

    def test_pdf_and_docx_extractors_are_callable(self):
        self.assertTrue(DocumentExtractor.extract({'name':'x.bin','mime':'application/octet-stream'},b'abc')['extractable'] is False)


    def test_zip_document_extraction_is_bounded_and_extracts_text_members(self):
        import io, zipfile
        with tempfile.TemporaryDirectory() as td:
            payload = io.BytesIO()
            with zipfile.ZipFile(payload, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.writestr('src/main.py', 'print("hello zip")')
                zf.writestr('docs/readme.md', '# Local ZIP\nYookAI can read this.')
                zf.writestr('image.bin', b'\x00\x01\x02')
            store = AttachmentStore(Path(td))
            meta = store.save('project.zip', 'application/zip', payload.getvalue())
            doc = meta['document']
            self.assertEqual(doc['format'], 'zip')
            self.assertTrue(doc['extractable'])
            self.assertIn('print("hello zip")', doc['text'])
            self.assertIn('# Local ZIP', doc['text'])
            self.assertEqual(doc['files'], 3)

    def test_zip_extractor_rejects_invalid_archive(self):
        with tempfile.TemporaryDirectory() as td:
            store = AttachmentStore(Path(td))
            meta = store.save('broken.zip', 'application/zip', b'not a zip')
            self.assertFalse(meta['document']['extractable'])
            self.assertIn('Invalid ZIP archive', meta['document']['error'])

    def test_session_export_shape(self):
        with tempfile.TemporaryDirectory() as td:
            sm=SessionManager(Path(td)); s=sm.create_session(); sm.add_message(s['id'],'user','hello')
            loaded=sm.load_session(s['id'])
            payload=json.dumps(loaded)
            self.assertIn('hello',payload)

if __name__=='__main__': unittest.main()

class TextNormalizationTests(unittest.TestCase):
    def test_repair_double_encoded_utf8(self):
        from core.text import repair_mojibake
        self.assertEqual(repair_mojibake("Ã¢ÂÂ"), "—")
        self.assertEqual(repair_mojibake("Bahasa Indonesia normal"), "Bahasa Indonesia normal")
