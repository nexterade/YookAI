import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"


class FrontendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = (TEMPLATES / "partials" / "model-selector.html").read_text(encoding="utf-8")
        cls.thinking = (TEMPLATES / "partials" / "thinking-block.html").read_text(encoding="utf-8")
        cls.app = (TEMPLATES / "app.js").read_text(encoding="utf-8")
        cls.css = (TEMPLATES / "style.css").read_text(encoding="utf-8")
        cls.api = (TEMPLATES / "api.js").read_text(encoding="utf-8")
        cls.index = (TEMPLATES / "index.html").read_text(encoding="utf-8")
        cls.base = (TEMPLATES / "_shared" / "base.html").read_text(encoding="utf-8")

    def test_model_selector_required_markup(self):
        for value in ('id="model-selector"', 'id="model-dropdown"', 'id="model-search"', 'id="model-list-recommended"'):
            self.assertIn(value, self.model)

    def test_thinking_block_required_markup(self):
        self.assertIn('class="thinking-block"', self.thinking)
        self.assertIn('data-thinking-body', self.thinking)
        self.assertIn('data-thinking-timer', self.thinking)

    def test_app_modules(self):
        self.assertRegex(self.app, r"const\s+ModelSelector\s*=")
        self.assertRegex(self.app, r"const\s+ThinkingBlock\s*=")
        self.assertRegex(self.app, r"const\s+RECOMMENDED\s*=")

    def test_css_selectors(self):
        for selector in ('.model-selector', '.model-dropdown', '.thinking-block', '.thinking-summary'):
            self.assertIn(selector, self.css)

    def test_api_list_models(self):
        self.assertIn('listModels', self.api)
        self.assertIn("/api/providers/${encodeURIComponent(provider)}/models", self.api)

    def test_index_extends_shared_base(self):
        self.assertRegex(self.index, r"\{\%\s*extends\s+['_\"]_shared/base\.html['_\"]\s*%\}")


    def test_start_page_and_refresh_resume_policy(self):
        app = (TEMPLATES / "app.js").read_text(encoding="utf-8")
        self.assertIn("ACTIVE_SESSION_KEY = 'yookai-active-session'", app)
        self.assertIn("SERVER_INSTANCE_KEY = 'yookai-server-instance'", app)
        self.assertIn("const isReload = nav?.type === 'reload'", app)
        self.assertIn("priorServer === serverInstance && isReload", app)
        self.assertIn("updateSidebarActive(null)", app)
        self.assertIn("sessionStorage.removeItem(ACTIVE_SESSION_KEY)", app)

    def test_base_has_anti_fouc_script(self):
        self.assertIn("localStorage.getItem('yookai-theme')", self.base)
        self.assertIn("prefers-color-scheme: dark", self.base)
        self.assertIn("data-theme", self.base)


# PR X static checks
class FrontendPolishTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = (TEMPLATES / "index.html").read_text(encoding="utf-8")
        cls.base = (TEMPLATES / "_shared" / "base.html").read_text(encoding="utf-8")
        cls.app = (TEMPLATES / "app.js").read_text(encoding="utf-8")
        cls.css = (TEMPLATES / "style.css").read_text(encoding="utf-8")
        cls.model = (TEMPLATES / "partials" / "model-selector.html").read_text(encoding="utf-8")
        cls.thinking = (TEMPLATES / "partials" / "thinking-block.html").read_text(encoding="utf-8")
        cls.api = (TEMPLATES / "api.js").read_text(encoding="utf-8")
        cls.empty = (TEMPLATES / "partials" / "empty-state.html").read_text(encoding="utf-8")

    def test_anti_fouc_and_jinja_comment_configuration_markers(self):
        self.assertIn("localStorage.getItem('yookai-theme')", self.base)
        self.assertIn("prefers-color-scheme: dark", self.base)
        self.assertIn("{% block styles %}", self.base)
        self.assertIn("{% include 'style.css' %}", self.index)

    def test_model_selector_keyboard_nav(self):
        self.assertRegex(self.app, r"handleKeydown\(e\)")
        self.assertIn("ArrowDown", self.app)
        self.assertIn("ArrowUp", self.app)
        self.assertIn("Escape", self.app)

    def test_thinking_timer_and_finalize(self):
        self.assertIn("startTimer(block)", self.app)
        self.assertIn("formatDuration(ms)", self.app)
        self.assertIn("setTimeout(() =>", self.app)

    def test_toast_auto_dismiss(self):
        self.assertRegex(self.app, r"setTimeout\(hideToast,\s*2200\)")

    def test_empty_state_variants_are_present_in_frontend(self):
        self.assertIn("session-empty", self.app)
        self.assertIn("model-empty", self.model)
        self.assertIn("error-state", self.app)
        self.assertIn("empty-state", self.empty)

    def test_touch_accessibility_and_reduced_motion_css(self):
        self.assertIn(":focus-visible", self.css)
        self.assertIn("prefers-reduced-motion:reduce", self.css)
        self.assertIn("min-height:44px", self.css)
        self.assertIn("safe-area-inset-bottom", self.css)

    def test_audit_features_markup(self):
        self.assertIn('id="attachment-input"', (TEMPLATES / 'partials' / 'composer.html').read_text(encoding='utf-8'))
        self.assertIn('id="stats-modal"', self.index)
        self.assertIn('id="settings-memory-mode"', self.index)
        self.assertIn('id="sidebar-collapse"', (TEMPLATES / 'partials' / 'sidebar.html').read_text(encoding='utf-8'))
        self.assertIn("uploadAttachment", self.api)
        self.assertIn("getSessionStats", self.api)

    def test_version_meta_present(self):
        self.assertIn('application-version" content="0.3.8"', self.base)
        self.assertIn('v0.3.8', (TEMPLATES / "partials" / "sidebar.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

class V021PolishTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = (TEMPLATES / "app.js").read_text(encoding="utf-8")
        cls.css = (TEMPLATES / "style.css").read_text(encoding="utf-8")
        cls.thinking = (TEMPLATES / "partials" / "thinking-block.html").read_text(encoding="utf-8")
        cls.header = (TEMPLATES / "partials" / "header.html").read_text(encoding="utf-8")
        cls.composer = (TEMPLATES / "partials" / "composer.html").read_text(encoding="utf-8")

    def test_thinking_spinner_is_present_and_starts_before_first_chunk(self):
        self.assertIn('class="thinking-spinner"', self.thinking)
        self.assertIn('let thinking = ThinkingBlock.create(aiRow);', self.app)
        self.assertIn('send-btn.loading::after', self.css)

    def test_ui_icons_use_svg_not_legacy_unicode_glyphs(self):
        for source in (self.header, self.composer):
            self.assertIn('<svg', source)
        for glyph in ('⧉', '✎', '↻', '↗', '☆', '⋯', '☰', '⚙', '＋'):
            self.assertNotIn(glyph, self.app + self.header + self.composer)

    def test_mojibake_repair_exists_at_render_boundary(self):
        self.assertIn('repairMojibake', self.app)
        self.assertIn('repairMojibake(msg.content', self.app)

class FinalMobileRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = (TEMPLATES / "app.js").read_text(encoding="utf-8")
        cls.css = (TEMPLATES / "style.css").read_text(encoding="utf-8")

    def test_assistant_avatar_removed_from_render_markup(self):
        self.assertNotIn('class="ai-avatar"', self.app)
        self.assertIn('.ai-avatar{display:none!important}', self.css)

    def test_stream_completion_releases_composer_before_session_save(self):
        completion = self.app.index("state.messages[aiIndex].completed_at =")
        release = self.app.index("state.isStreaming = false;", completion)
        persist = self.app.index("await saveSession();", completion)
        self.assertLess(release, persist)
        self.assertIn("send.hidden = streaming", self.app)

class ThinkingPersistenceRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = (TEMPLATES / "app.js").read_text(encoding="utf-8")

    def test_completed_thinking_is_not_hidden(self):
        self.assertNotIn("thinking.hidden = true", self.app)
        self.assertNotIn("if (msg.completed_at) block.hidden = true", self.app)

    def test_thinking_is_finalized_on_done_and_stop(self):
        self.assertIn("// Preserve the thinking transcript after completion; only stop its live timer/animation.", self.app)
        self.assertIn("document.querySelectorAll('.thinking-block').forEach((block) => ThinkingBlock.finalize(block));", self.app)

    def test_reasoning_content_remains_under_thinking_label(self):
        self.assertIn("if (label) label.textContent = 'Thinking';", self.app)
        self.assertIn("body.innerHTML = window.renderMarkdown ? renderMarkdown(body.dataset.raw)", self.app)
