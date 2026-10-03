"""Local document extraction for YookAI attachments.

The extractor is deliberately in-memory and bounded so archives cannot write files
or escape the attachment sandbox. ZIP archives are treated as document containers,
not executable projects.
"""
from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import Path
from typing import Any


class DocumentExtractor:
    MAX_CHARS = 120_000
    MAX_ARCHIVE_FILES = 200
    MAX_ARCHIVE_BYTES = 40 * 1024 * 1024
    MAX_MEMBER_BYTES = 10 * 1024 * 1024
    MAX_NESTED_ARCHIVE_DEPTH = 1
    TEXT_SUFFIXES = {
        '.txt', '.md', '.csv', '.json', '.xml', '.html', '.htm', '.css', '.js',
        '.ts', '.tsx', '.jsx', '.py', '.pyw', '.java', '.c', '.h', '.cpp', '.hpp',
        '.go', '.rs', '.rb', '.php', '.sh', '.bash', '.zsh', '.ps1', '.log', '.yaml',
        '.yml', '.toml', '.ini', '.cfg', '.conf', '.sql', '.env', '.vue', '.svelte',
    }

    @classmethod
    def _decode_text(cls, data: bytes) -> str:
        # UTF-8 first; UTF-8 with replacement is preferable to silently losing bytes.
        return data.decode('utf-8', errors='replace')

    @classmethod
    def _extract_single(cls, name: str, mime: str, data: bytes, *, allow_archive: bool = True) -> dict[str, Any]:
        suffix = Path(name).suffix.lower()
        try:
            if mime.startswith('text/') or mime in {'application/json', 'application/xml', 'application/javascript'} or suffix in cls.TEXT_SUFFIXES:
                text = cls._decode_text(data)
            elif allow_archive and (suffix == '.zip' or mime in {'application/zip', 'application/x-zip-compressed'}):
                return cls._extract_zip(data)
            elif suffix == '.pdf' or mime == 'application/pdf':
                from pypdf import PdfReader
                reader = PdfReader(io.BytesIO(data))
                text = '\n\n'.join((page.extract_text() or '') for page in reader.pages)
            elif suffix == '.docx' or mime == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
                from docx import Document
                doc = Document(io.BytesIO(data))
                text = '\n'.join(p.text for p in doc.paragraphs)
                for table in doc.tables:
                    for row in table.rows:
                        text += '\n' + '\t'.join(cell.text for cell in row.cells)
            elif suffix in {'.xlsx', '.xlsm'} or 'spreadsheetml' in mime:
                from openpyxl import load_workbook
                wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
                chunks = []
                for ws in wb.worksheets:
                    chunks.append(f'# Sheet: {ws.title}')
                    for row in ws.iter_rows(values_only=True):
                        vals = ['' if v is None else str(v) for v in row]
                        if any(vals):
                            chunks.append('\t'.join(vals))
                text = '\n'.join(chunks)
            else:
                return {'extractable': False, 'text': '', 'chars': 0, 'format': suffix.lstrip('.') or mime}
        except Exception as exc:
            return {'extractable': False, 'text': '', 'chars': 0, 'format': suffix.lstrip('.') or mime, 'error': str(exc)}

        text = text.replace('\x00', '').strip()
        if len(text) > cls.MAX_CHARS:
            text = text[:cls.MAX_CHARS] + '\n… [truncated]'
        return {'extractable': bool(text), 'text': text, 'chars': len(text), 'format': suffix.lstrip('.') or mime}

    @classmethod
    def _safe_member_name(cls, name: str) -> str:
        # We never extract to disk, but reject suspicious path components in the
        # generated report so archive metadata cannot become an apparent local path.
        parts = [p for p in name.replace('\\', '/').split('/') if p not in ('', '.')]
        safe = '/'.join(p for p in parts if p != '..')
        return safe or 'unnamed'

    @classmethod
    def _read_member_bounded(cls, archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> bytes:
        if info.file_size < 0 or info.file_size > cls.MAX_MEMBER_BYTES:
            raise ValueError(f'ZIP member exceeds {cls.MAX_MEMBER_BYTES // (1024 * 1024)} MB limit')
        remaining = info.file_size
        chunks: list[bytes] = []
        with archive.open(info, 'r') as handle:
            while remaining:
                chunk = handle.read(min(64 * 1024, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
        data = b''.join(chunks)
        if len(data) != info.file_size:
            raise ValueError('ZIP member ended before its declared size')
        return data

    @classmethod
    def _extract_zip(cls, data: bytes) -> dict[str, Any]:
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                infos = [info for info in archive.infolist() if not info.is_dir()]
                if len(infos) > cls.MAX_ARCHIVE_FILES:
                    raise ValueError(f'ZIP contains more than {cls.MAX_ARCHIVE_FILES} files')
                declared_total = sum(max(0, info.file_size) for info in infos)
                if declared_total > cls.MAX_ARCHIVE_BYTES:
                    raise ValueError('ZIP uncompressed content exceeds 40 MB limit')

                chunks: list[str] = [f'# ZIP archive ({len(infos)} files)']
                total_read = 0
                extracted_files = 0
                skipped_files = 0
                for info in infos:
                    name = cls._safe_member_name(info.filename)
                    if not name:
                        continue
                    try:
                        member = cls._read_member_bounded(archive, info)
                        total_read += len(member)
                        if total_read > cls.MAX_ARCHIVE_BYTES:
                            raise ValueError('ZIP uncompressed content exceeds 40 MB limit')
                        mime = __import__('mimetypes').guess_type(name)[0] or 'application/octet-stream'
                        result = cls._extract_single(name, mime, member, allow_archive=False)
                        if result.get('extractable'):
                            chunks.append(f'\n## {name}\n{result["text"]}')
                            extracted_files += 1
                        else:
                            chunks.append(f'\n## {name}\n[Binary or unsupported file: {info.file_size} bytes]')
                            skipped_files += 1
                    except Exception as exc:
                        chunks.append(f'\n## {name}\n[Skipped: {exc}]')
                        skipped_files += 1

                text = '\n'.join(chunks).strip()
                if len(text) > cls.MAX_CHARS:
                    text = text[:cls.MAX_CHARS] + '\n… [truncated]'
                return {
                    'extractable': bool(text),
                    'text': text,
                    'chars': len(text),
                    'format': 'zip',
                    'files': len(infos),
                    'extracted_files': extracted_files,
                    'skipped_files': skipped_files,
                }
        except zipfile.BadZipFile as exc:
            return {'extractable': False, 'text': '', 'chars': 0, 'format': 'zip', 'error': f'Invalid ZIP archive: {exc}'}
        except Exception as exc:
            return {'extractable': False, 'text': '', 'chars': 0, 'format': 'zip', 'error': str(exc)}

    @classmethod
    def extract(cls, meta: dict[str, Any], data: bytes) -> dict[str, Any]:
        name = meta.get('name', 'attachment')
        mime = meta.get('mime', 'application/octet-stream')
        suffix = Path(name).suffix.lower()
        # CSV gets normalized to tabular text rather than being returned verbatim.
        if suffix == '.csv' or mime == 'text/csv':
            try:
                raw = cls._decode_text(data)
                rows = list(csv.reader(io.StringIO(raw)))
                text = '\n'.join('\t'.join(row) for row in rows)
                if len(text) > cls.MAX_CHARS:
                    text = text[:cls.MAX_CHARS] + '\n… [truncated]'
                return {'extractable': bool(text.strip()), 'text': text.strip(), 'chars': len(text.strip()), 'format': 'csv'}
            except Exception as exc:
                return {'extractable': False, 'text': '', 'chars': 0, 'format': 'csv', 'error': str(exc)}
        return cls._extract_single(name, mime, data)
