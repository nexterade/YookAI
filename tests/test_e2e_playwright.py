import os, subprocess, tempfile, time, unittest
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]

class BrowserSmokeTests(unittest.TestCase):
    def test_ui_smoke(self):
        with tempfile.TemporaryDirectory() as td:
            env=os.environ.copy(); env['HOME']=td
            proc=subprocess.Popen(['python',str(ROOT/'server.py'),'--host','127.0.0.1','--port','8765','--no-open'],cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
            try:
                for _ in range(50):
                    try:
                        import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/',timeout=.2); break
                    except Exception: time.sleep(.1)
                with sync_playwright() as p:
                    browser=p.chromium.launch(headless=True, executable_path="/usr/bin/chromium", args=["--no-sandbox"])
                    page=browser.new_page(viewport={'width':1280,'height':800})
                    try:
                        page.goto('http://127.0.0.1:8765/',wait_until='domcontentloaded')
                    except Exception as exc:
                        if 'ERR_BLOCKED_BY_ADMINISTRATOR' in str(exc):
                            self.skipTest('Browser network navigation is blocked by the execution sandbox')
                        raise
                    self.assertIn('YookAI',page.title())
                    self.assertTrue(page.locator('#composer-input').is_visible())
                    page.locator('#toggle-sidebar').click()
                    page.locator('#open-memory').click()
                    self.assertTrue(page.locator('#memory-modal').is_visible())
                    page.locator('#close-memory').click()
                    page.locator('#open-stats').click()
                    self.assertTrue(page.locator('#stats-modal').is_visible())
                    page.locator('#close-stats').click()
                    page.locator('#open-search').click()
                    self.assertTrue(page.locator('#search-modal').is_visible())
                    browser.close()
            finally:
                proc.terminate(); proc.wait(timeout=5)

if __name__=='__main__': unittest.main()
