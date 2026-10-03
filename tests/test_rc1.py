
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_rc1_version_and_assets():
    html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "templates" / "style.css").read_text(encoding="utf-8")
    js = (ROOT / "templates" / "app.js").read_text(encoding="utf-8")
    assert "0.3.0-final" in (ROOT / "app" / "server.py").read_text(encoding="utf-8")
    assert "send-btn.loading" in css
    assert "StreamRender" in js
    assert "prefers-reduced-motion" in css

def test_no_runtime_emoji_attachment_icons():
    js = (ROOT / "templates" / "app.js").read_text(encoding="utf-8")
    # Attachment chips use the shared SVG registry rather than Unicode pictograms.
    assert "SVG.paperclip" in js
    assert "SVG.archive" in js
    assert "SVG.image" in js

def test_sse_stream_ownership_is_safe():
    sse = (ROOT / "app" / "sse.py").read_text(encoding="utf-8")
    assert "self.wfile.close()" not in sse
    assert "BaseHTTPRequestHandler" in sse

def test_streaming_render_is_frame_coalesced():
    js = (ROOT / "templates" / "app.js").read_text(encoding="utf-8")
    assert "requestAnimationFrame" in js
    assert "StreamRender.schedule" in js
    assert "StreamRender.cancel" in js
