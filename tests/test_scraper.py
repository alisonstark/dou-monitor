import unittest
import re
import sys
from pathlib import Path

# Add src to path so we can import the modules
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))


class TestTitleCleaning(unittest.TestCase):
    """Test the title cleaning logic from scraper.py"""

    def clean_title(self, title):
        """Replicate the cleaning logic from scraper.py"""
        # Extract content from HTML span tags and remove the tags
        title = re.sub(r'<span[^>]*>(.*?)</span>', r'\1', title)
        # Remove consecutive duplicate words (case-insensitive)
        title = re.sub(r'(\w+)(?:\s*\1)+', r'\1', title, flags=re.IGNORECASE)
        return title

    def test_remove_html_spans(self):
        """Test that HTML span tags are removed but content is preserved"""
        title = "EDITAL <span class='highlight'>CONCURSO</span> PÚBLICO"
        expected = "EDITAL CONCURSO PÚBLICO"
        self.assertEqual(self.clean_title(title), expected)

    def test_remove_duplicate_words(self):
        """Test that duplicate words are removed"""
        title = "EDITAL EDITAL CONCURSO"
        expected = "EDITAL CONCURSO"
        self.assertEqual(self.clean_title(title), expected)

    def test_remove_spans_with_duplicates(self):
        """Test the real case: duplicate span tags are deduplicated"""
        title = "EDITAL DE ABERTURA DE 10 DE FEVEREIRO DE 2026 <span class='highlight' style='background:#FFA;'>CONCURSO</span><span class='highlight' style='background:#FFA;'>CONCURSO</span> PÚBLICO PARA PROVIMENTO DE CARGOS"
        result = self.clean_title(title)
        # Should not have duplicate CONCURSO
        self.assertEqual(result.count('CONCURSO'), 1)
        # Should contain the full text
        self.assertIn('EDITAL', result)
        self.assertIn('CONCURSO', result)
        self.assertIn('PÚBLICO', result)

    def test_case_insensitive_duplicates(self):
        """Test that duplicate removal works case-insensitively"""
        title = "EDITAL Edital edital CONCURSO"
        expected = "EDITAL CONCURSO"
        self.assertEqual(self.clean_title(title), expected)

    def test_empty_string(self):
        """Test that empty strings are handled"""
        self.assertEqual(self.clean_title(""), "")

    def test_no_changes_needed(self):
        """Test that clean titles pass through unchanged"""
        title = "EDITAL DE ABERTURA CONCURSO PÚBLICO"
        self.assertEqual(self.clean_title(title), title)

    def test_multiple_spans_different_content(self):
        """Test that different span contents are preserved"""
        title = "<span>EDITAL</span> de <span>ABERTURA</span>"
        expected = "EDITAL de ABERTURA"
        self.assertEqual(self.clean_title(title), expected)


if __name__ == '__main__':
    unittest.main()
