import atexit
import os

from playwright.sync_api import sync_playwright

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/121.0.0.0 Safari/537.36"
)

_playwright = None
_browser = None
_context = None


def _get_browser_context():
    global _playwright, _browser, _context

    if _context is None:
        _playwright = sync_playwright().start()
        _browser = _playwright.chromium.launch()
        _context = _browser.new_context(
            user_agent=USER_AGENT,
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
        )

    return _context


def _close_browser_context():
    global _playwright, _browser, _context

    if _context is not None:
        _context.close()
        _context = None
    if _browser is not None:
        _browser.close()
        _browser = None
    if _playwright is not None:
        _playwright.stop()
        _playwright = None


atexit.register(_close_browser_context)


def save_concurso_pdf(concurso, output_dir="editais"):
    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.join(output_dir, f"{concurso['url_title']}.pdf")

    context = _get_browser_context()
    page = context.new_page()
    try:
        page.goto(concurso['url'], wait_until="networkidle")
        page.emulate_media(media="print")
        page.pdf(
            path=filename,
            format="A4",
            print_background=True,
            prefer_css_page_size=True,
        )
    finally:
        page.close()

    return f"Content saved to {filename}"
