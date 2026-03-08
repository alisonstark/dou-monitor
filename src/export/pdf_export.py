import os
from contextlib import contextmanager

from playwright.sync_api import sync_playwright

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/121.0.0.0 Safari/537.36"
)


@contextmanager
def _playwright_context():
    """
    Context manager for Playwright browser instance.
    Creates a new instance per use to avoid thread conflicts in Flask debug mode.
    """
    playwright = None
    browser = None
    context = None
    try:
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=USER_AGENT,
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
        )
        yield context
    finally:
        # Clean up in reverse order
        if context is not None:
            try:
                context.close()
            except Exception:
                pass
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
        if playwright is not None:
            try:
                playwright.stop()
            except Exception:
                pass


def save_concurso_pdf(concurso, output_dir="editais", output_path=None):
    """
    Download PDF from DOU using Playwright.
    
    Args:
        concurso: Dict with 'url' and 'url_title' keys
        output_dir: Directory to save PDF (used when output_path is None)
        output_path: Full path to save PDF (overrides output_dir)
    
    Returns:
        Success message string or error message string starting with "Error"
    """
    if output_path:
        filename = output_path
        parent = os.path.dirname(filename)
        if parent:
            os.makedirs(parent, exist_ok=True)
    else:
        os.makedirs(output_dir, exist_ok=True)
        filename = os.path.join(output_dir, f"{concurso['url_title']}.pdf")

    # If file exists and is locked, try to remove it first
    if os.path.exists(filename):
        try:
            os.remove(filename)
        except PermissionError:
            return f"Error: File is locked or in use: {filename}\nClose any PDF viewer that has this file open and try again."
        except Exception as e:
            return f"Error removing old file: {e}"

    # Use context manager to ensure cleanup
    try:
        with _playwright_context() as context:
            page = context.new_page()
            try:
                response = page.goto(concurso['url'], wait_until="networkidle", timeout=30000)
                if response is not None and response.status >= 400:
                    return f"Error saving PDF: DOU returned HTTP {response.status} for URL {concurso['url']}"

                # Some DOU not-found pages can return 200; detect by page text before printing.
                page_text = page.content().lower()
                if (
                    "estado" in page_text
                    and "não encontrado" in page_text
                    and "o recurso requisitado não foi encontrado" in page_text
                ):
                    return f"Error saving PDF: DOU page indicates resource not found for URL {concurso['url']}"

                page.emulate_media(media="print")
                page.pdf(
                    path=filename,
                    format="A4",
                    print_background=True,
                    prefer_css_page_size=True,
                )
            finally:
                page.close()
    except PermissionError:
        return f"Error: Permission denied writing to {filename}\nEnsure the file is not open in another application."
    except Exception as e:
        return f"Error saving PDF: {e}"

    return f"Content saved to {filename}"
