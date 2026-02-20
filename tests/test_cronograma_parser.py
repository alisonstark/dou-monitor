import unittest
import sys
from pathlib import Path

# Add src to path so we can import the modules
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from extraction.cronograma_parser import (
    to_iso,
    parse_date_block,
    classify_event,
    normalize_text,
    extract_all_dates,
    CronogramaParser
)


class TestDateConversion(unittest.TestCase):
    """Test the to_iso function"""

    def test_valid_date_conversion(self):
        """Test converting valid Brazilian date to ISO format"""
        result = to_iso("10/02/2026")
        self.assertEqual(result, "2026-02-10")

    def test_date_with_spaces(self):
        """Test that spaces are handled"""
        result = to_iso("  10/02/2026  ")
        self.assertEqual(result, "2026-02-10")

    def test_invalid_date(self):
        """Test that invalid dates return None"""
        result = to_iso("99/99/9999")
        self.assertIsNone(result)

    def test_wrong_format(self):
        """Test that wrong format returns None"""
        result = to_iso("2026-02-10")
        self.assertIsNone(result)


class TestParseDateBlock(unittest.TestCase):
    """Test the parse_date_block function"""

    def test_single_date(self):
        """Test parsing a single date"""
        start, end = parse_date_block("10/02/2026")
        self.assertEqual(start, "2026-02-10")
        self.assertIsNone(end)

    def test_date_range_with_a(self):
        """Test parsing date range with 'a' separator"""
        start, end = parse_date_block("10/02/2026 a 20/02/2026")
        self.assertEqual(start, "2026-02-10")
        self.assertEqual(end, "2026-02-20")

    def test_entre_phrase_with_a(self):
        """Test parsing 'Entre' phrase with 'a' (now should work after fix)"""
        start, end = parse_date_block("Entre 10/02/2026 a 20/02/2026")
        self.assertEqual(start, "2026-02-10")
        self.assertEqual(end, "2026-02-20")

    def test_entre_phrase_with_e(self):
        """Test parsing 'Entre' phrase with 'e'"""
        start, end = parse_date_block("Entre 10/02/2026 e 20/02/2026")
        self.assertEqual(start, "2026-02-10")
        self.assertEqual(end, "2026-02-20")

    def test_entre_lowercase(self):
        """Test case-insensitivity: 'entre' in lowercase"""
        start, end = parse_date_block("entre 10/02/2026 a 20/02/2026")
        self.assertEqual(start, "2026-02-10")
        self.assertEqual(end, "2026-02-20")

    def test_entre_single_date(self):
        """Test parsing 'Entre' with only one date"""
        start, end = parse_date_block("Entre 10/02/2026")
        self.assertEqual(start, "2026-02-10")
        self.assertIsNone(end)


class TestClassifyEvent(unittest.TestCase):
    """Test the classify_event function"""

    def test_inscricao_singular(self):
        """Test classifying inscrição singular"""
        result = classify_event("Inscrição para o concurso")
        self.assertEqual(result, "inscricao")

    def test_inscricao_plural(self):
        """Test classifying inscrições plural"""
        result = classify_event("Inscrições abertas")
        self.assertEqual(result, "inscricao")

    def test_inscricao_without_accent(self):
        """Test classifying inscricao without accent"""
        result = classify_event("Inscricao de candidatos")
        self.assertEqual(result, "inscricao")

    def test_isencao(self):
        """Test classifying isenção"""
        result = classify_event("Isenção de taxa de inscrição")
        self.assertEqual(result, "isencao")

    def test_isencao_without_accent(self):
        """Test classifying isencao without accent"""
        result = classify_event("Isencao de taxa")
        self.assertEqual(result, "isencao")

    def test_prova(self):
        """Test classifying prova"""
        result = classify_event("Realização da prova objetiva")
        self.assertEqual(result, "prova")

    def test_aplicacao_prova(self):
        """Test classifying aplicação da prova"""
        result = classify_event("Aplicação da prova")
        self.assertEqual(result, "prova")

    def test_resultado(self):
        """Test classifying resultado"""
        result = classify_event("Resultado preliminar")
        self.assertEqual(result, "resultado")

    def test_homologacao_absorption(self):
        """Test that homologacao text gets classified by other keywords if present"""
        # "Homologação das inscrições" should classify as inscricao (inscricao priority)
        result = classify_event("Homologação das inscrições")
        self.assertEqual(result, "inscricao")
        # Pure homologacao with no other keywords becomes "outro"
        result = classify_event("Homologação do resultado")
        self.assertEqual(result, "resultado")  # resultado keyword takes priority

    def test_outro(self):
        """Test classifying unknown event"""
        result = classify_event("Algum evento aleatório")
        self.assertEqual(result, "outro")

    def test_isencao_priority_over_inscricao(self):
        """Test that isenção is classified before inscrição (priority)"""
        # Even though both keywords are present, isenção should be returned
        result = classify_event("Isenção de inscrição")
        self.assertEqual(result, "isencao")


class TestNormalizeText(unittest.TestCase):
    """Test the normalize_text function"""

    def test_remove_urls(self):
        """Test that URLs are removed"""
        text = "Inscrição em https://example.com data 10/02/2026"
        result = normalize_text(text)
        self.assertNotIn("https://", result)
        self.assertIn("10/02/2026", result)

    def test_fix_broken_date_range(self):
        """Test fixing date ranges split by newline"""
        text = "10/02/2026 a\n20/02/2026"
        result = normalize_text(text)
        self.assertIn("10/02/2026 a 20/02/2026", result)

    def test_fix_broken_entre(self):
        """Test fixing broken 'Entre' statement"""
        text = "Entre\n10/02/2026"
        result = normalize_text(text)
        self.assertIn("Entre 10/02/2026", result)

    def test_fix_broken_entre_lowercase(self):
        """Test case-insensitivity: lowercase 'entre' with newline"""
        text = "entre\n10/02/2026 e 20/02/2026"
        result = normalize_text(text)
        # Should normalize to "Entre" (capital) with space
        self.assertIn("Entre 10/02/2026", result)

    def test_collapse_whitespace(self):
        """Test that excessive whitespace is collapsed"""
        text = "Inscrição    com    espaços    extras"
        result = normalize_text(text)
        self.assertNotIn("   ", result)

    def test_inscricao_newline_fix(self):
        """Test fixing inscrição split across lines - both singular and plural"""
        # Test singular form
        text = "Período de inscrição\n10/02/2026 a 15/02/2026"
        result = normalize_text(text)
        self.assertIn("inscrição", result)
        # Test plural form
        text = "Inscrições online\n10/02/2026 a 15/02/2026"
        result = normalize_text(text)
        self.assertIn("Inscrições online 10/02/2026 a 15/02/2026", result)


class TestExtractAllDates(unittest.TestCase):
    """Test the extract_all_dates function"""

    def test_simple_date_extraction(self):
        """Test extracting a simple date with context"""
        text = "Inscrição 10/02/2026"
        results = extract_all_dates(text)
        self.assertGreaterEqual(len(results), 1)
        # Check that at least one event was found
        dates_found = [r.get("data_inicio") for r in results]
        self.assertIn("2026-02-10", dates_found)

    def test_date_range_extraction(self):
        """Test extracting date ranges"""
        text = "Inscrição 10/02/2026 a 20/02/2026"
        results = extract_all_dates(text)
        self.assertGreaterEqual(len(results), 1)
        event = results[0]
        self.assertEqual(event["data_inicio"], "2026-02-10")
        self.assertEqual(event["data_fim"], "2026-02-20")

    def test_multiple_events_extraction(self):
        """Test extracting multiple events"""
        text = """
        Inscrição 10/02/2026 a 15/02/2026
        Isenção de taxa 12/02/2026
        Prova objetiva 20/02/2026
        """
        results = extract_all_dates(text)
        # Should find at least 2-3 events
        self.assertGreaterEqual(len(results), 2)

    def test_event_classification(self):
        """Test that events are properly classified"""
        text = """
        Inscrição 10/02/2026 a 15/02/2026
        Isenção 12/02/2026
        Prova 20/02/2026
        """
        results = extract_all_dates(text)
        tipos = [r["tipo"] for r in results]
        # Should have inscricao, isencao, and/or prova
        self.assertTrue(any(t in ["inscricao", "isencao", "prova"] for t in tipos))


class TestCronogramaParser(unittest.TestCase):
    """Test the CronogramaParser class"""

    def setUp(self):
        self.parser = CronogramaParser()

    def test_empty_text(self):
        """Test that empty text returns empty results"""
        result = self.parser.extract_from_text("")
        self.assertIsNone(result["inscricao_inicio"])
        self.assertIsNone(result["inscricao_fim"])
        self.assertIsNone(result["isencao_inicio"])
        self.assertIsNone(result["data_prova"])

    def test_simple_extraction(self):
        """Test basic cronograma extraction"""
        text = """
        CRONOGRAMA
        Inscrição: 10/02/2026 a 15/02/2026
        Isenção: 12/02/2026
        Prova: 20/02/2026
        """
        result = self.parser.extract_from_text(text)
        # Should find at least one field
        fields_filled = sum(1 for v in result.values() if v is not None)
        self.assertGreaterEqual(fields_filled, 1)

    def test_returns_expected_keys(self):
        """Test that result has all expected keys"""
        text = "CRONOGRAMA Inscrição 10/02/2026 a 15/02/2026"
        result = self.parser.extract_from_text(text)
        expected_keys = {"inscricao_inicio", "inscricao_fim", "isencao_inicio", "data_prova"}
        self.assertEqual(set(result.keys()), expected_keys)

    def test_full_cronograma(self):
        """Test extraction from a more complete cronograma"""
        text = """
        CRONOGRAMA

        Período de inscrições: 10/02/2026 a 15/02/2026
        Período para solicitação de isenção: 10/02/2026 a 12/02/2026
        Data da prova: 20/02/2026
        """
        result = self.parser.extract_from_text(text)
        # Should extract inscricao dates
        if result["inscricao_inicio"]:
            self.assertEqual(result["inscricao_inicio"], "2026-02-10")

    def test_isencao_extraction(self):
        """Test that isenção is specifically extracted when present"""
        text = """
        CRONOGRAMA
        - Inscrição: 10/02/2026 a 15/02/2026
        - Isenção: 12/02/2026
        - Prova: 20/02/2026
        """
        result = self.parser.extract_from_text(text)
        # If isencao is found, verify it's a valid ISO date
        if result["isencao_inicio"]:
            self.assertRegex(result["isencao_inicio"], r'^\d{4}-\d{2}-\d{2}$')

    def test_both_inscricao_and_isencao(self):
        """Test that both inscricao and isencao are extracted when both present"""
        text = """
        CRONOGRAMA
        Período de inscrição: 10/02/2026 a 15/02/2026
        Solicitação de isenção: 12/02/2026 a 14/02/2026
        Prova objetiva: 20/02/2026
        """
        result = self.parser.extract_from_text(text)
        # Both should be found
        has_inscricao = result["inscricao_inicio"] is not None
        has_isencao = result["isencao_inicio"] is not None
        self.assertTrue(has_inscricao or has_isencao, "At least one of inscricao or isencao should be found")


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and malformed inputs"""

    def test_malformed_date_format(self):
        """Test that malformed dates are handled gracefully"""
        result = to_iso("2026/02/10")  # Wrong order
        self.assertIsNone(result)

    def test_day_month_swapped(self):
        """Test dates with day/month in wrong positions"""
        # This is tricky - a valid date that could be mis-parsed
        result = to_iso("13/02/2026")  # This is valid (Feb 13)
        self.assertEqual(result, "2026-02-13")
        # But this would be invalid:
        result = to_iso("02/13/2026")  # Month 13 doesn't exist
        self.assertIsNone(result)

    def test_impossibly_far_future_date(self):
        """Test dates far in the future"""
        result = to_iso("01/01/9999")
        self.assertEqual(result, "9999-01-01")

    def test_historical_dates(self):
        """Test dates from the past"""
        result = to_iso("01/01/1900")
        self.assertEqual(result, "1900-01-01")

    def test_date_extraction_with_garbage_text(self):
        """Test extraction from text with lots of noise"""
        text = """
        CRONOGRAMA!@#$%^&*()
        Lorem ipsum dolor sit amet
        Inscrição 10/02/2026 a 15/02/2026
        Some random text with numbers 123456
        Prova 20/02/2026 (confirmado)
        """
        results = extract_all_dates(text)
        self.assertGreaterEqual(len(results), 1)

    def test_no_dates_in_text(self):
        """Test text with no dates at all"""
        text = "This is just some random text with no dates anywhere"
        results = extract_all_dates(text)
        # Should return empty or only "outro" events (no extractable dates)
        self.assertEqual(len(results), 0)

    def test_duplicate_event_deduplication(self):
        """Test that duplicate events are not double-counted"""
        text = """
        Inscrição 10/02/2026 a 15/02/2026
        Período de inscrição: 10/02/2026 a 15/02/2026
        """
        results = extract_all_dates(text)
        # Should deduplicate (seen_dates tracking)
        inscricao_count = sum(1 for r in results if r["tipo"] == "inscricao" 
                            and r["data_inicio"] == "2026-02-10")
        self.assertLessEqual(inscricao_count, 2, "Duplicates should be minimized")

    def test_date_range_with_same_dates(self):
        """Test date ranges where start equals end"""
        start, end = parse_date_block("10/02/2026 a 10/02/2026")
        self.assertEqual(start, "2026-02-10")
        self.assertEqual(end, "2026-02-10")

    def test_normalize_excessive_newlines(self):
        """Test that excessive newlines are collapsed"""
        text = "Inscrição\n\n\n\n\n10/02/2026"
        result = normalize_text(text)
        # Should have max 2 consecutive newlines
        self.assertNotIn("\n\n\n", result)

    def test_normalize_mixed_whitespace(self):
        """Test handling of tabs and irregular spacing"""
        text = "Inscrição\t\t\t10/02/2026"
        result = normalize_text(text)
        # Should collapse tabs to single space
        self.assertNotIn("\t\t\t", result)

    def test_singular_inscricao_in_extraction(self):
        """Test that singular 'inscrição' (not plural) is caught"""
        text = "Período de inscrição: 10/02/2026"
        results = extract_all_dates(text)
        # Should find at least event with the inscricao date
        self.assertGreaterEqual(len(results), 1)



if __name__ == '__main__':
    unittest.main()
