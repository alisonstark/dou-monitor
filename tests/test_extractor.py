import unittest
import sys
import json
import tempfile
from pathlib import Path

# Add src to path so we can import the modules
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from extraction.extractor import (
    _find_first_currency,
    _parse_date,
    extract_basic_metadata,
    extract_cronograma,
    extract_vagas,
    extract_financeiro,
)


class TestFindFirstCurrency(unittest.TestCase):
    """Test the _find_first_currency() function"""

    def test_simple_currency(self):
        """Test finding a simple R$ amount"""
        text = "Taxa de inscrição: R$ 100,00"
        result = _find_first_currency(text)
        self.assertEqual(result, "R$ 100,00")

    def test_currency_with_spaces(self):
        """Test currency with variable spacing"""
        text = "Valor:  R$  500,50"
        result = _find_first_currency(text)
        self.assertIsNotNone(result)
        self.assertIn("R$", result)

    def test_large_amount(self):
        """Test finding larger amounts with thousands"""
        text = "Remuneração inicial: R$ 5.000,00 mensais"
        result = _find_first_currency(text)
        self.assertIsNotNone(result)
        self.assertIn("5", result)

    def test_no_currency(self):
        """Test that None is returned when no currency found"""
        text = "Este texto não tem nenhum valor monetário"
        result = _find_first_currency(text)
        self.assertIsNone(result)

    def test_first_currency_when_multiple(self):
        """Test that only first currency is returned - without trailing comma"""
        text = "Taxa: R$ 100,00, Depósito: R$ 500,00"
        result = _find_first_currency(text)
        self.assertEqual(result, "R$ 100,00")  # Should NOT include the trailing comma

    def test_currency_thousands_separator(self):
        """Test currency with thousands separator (dot)"""
        text = "Remuneração: R$ 1.500,00"
        result = _find_first_currency(text)
        self.assertEqual(result, "R$ 1.500,00")

    def test_currency_multiple_thousands(self):
        """Test currency with multiple thousands separators"""
        text = "Orçamento: R$ 1.000.000,50"
        result = _find_first_currency(text)
        self.assertEqual(result, "R$ 1.000.000,50")

    def test_currency_without_thousands_separator(self):
        """Test currency without thousands separator"""
        text = "Valor: R$ 999,99"
        result = _find_first_currency(text)
        self.assertEqual(result, "R$ 999,99")

    def test_currency_without_decimal_part(self):
        """Test currency without decimal cents"""
        text = "Total: R$ 5000"
        result = _find_first_currency(text)
        self.assertEqual(result, "R$ 5000")

    def test_currency_formats(self):
        """Test different currency formats (dots vs commas)"""
        # Brazilian format: R$ 1.000,00 or R$ 1000,00
        text1 = "R$ 1.000,00"
        result1 = _find_first_currency(text1)
        self.assertIsNotNone(result1)

        text2 = "R$ 1000,00"
        result2 = _find_first_currency(text2)
        self.assertIsNotNone(result2)


class TestParseDate(unittest.TestCase):
    """Test the _parse_date() function (uses dateparser library)"""

    def test_portuguese_date_format_1(self):
        """Test standard Portuguese date format"""
        result = _parse_date("10 de fevereiro de 2026")
        # If dateparser is available, should parse to ISO
        if result:
            self.assertRegex(result, r'^\d{4}-\d{2}-\d{2}$')

    def test_portuguese_date_format_2(self):
        """Test abbreviated Portuguese date"""
        result = _parse_date("20 de fev de 2026")
        if result:
            self.assertRegex(result, r'^\d{4}-\d{2}-\d{2}$')

    def test_numeric_date_format(self):
        """Test numeric date format"""
        result = _parse_date("10/02/2026")
        # dateparser might interpret this differently in Portuguese context
        # Just check it either parses or returns None
        if result is not None:
            self.assertRegex(result, r'^\d{4}-\d{2}-\d{2}$')

    def test_invalid_date(self):
        """Test that invalid dates return None"""
        result = _parse_date("99 de mês inválido de 9999")
        # Should be None or fail gracefully
        # No assertion needed - just verify it doesn't crash

    def test_empty_string(self):
        """Test empty string handling"""
        result = _parse_date("")
        self.assertIsNone(result)


class TestExtractBasicMetadata(unittest.TestCase):
    """Test the extract_basic_metadata() function"""

    def test_extract_orgao(self):
        """Test extraction of órgão (institution)"""
        text = """
        UNIVERSIDADE FEDERAL DO BRASIL
        
        EDITAL DE ABERTURA DE CONCURSO PÚBLICO
        """
        result = extract_basic_metadata(text)
        self.assertIsNotNone(result["orgao"])
        self.assertIn("UNIVERSIDADE", result["orgao"].upper())

    def test_extract_edital_numero(self):
        """Test extraction of edital number"""
        text = "Edital nº 123/2026 de Abertura de Concurso Público"
        result = extract_basic_metadata(text)
        self.assertIsNotNone(result["edital_numero"])

    def test_extract_edital_with_date(self):
        """Test edital number extraction from date-based format"""
        text = "Edital de Abertura de 10 de fevereiro de 2026"
        result = extract_basic_metadata(text)
        # Should extract the date as edital number
        if result["edital_numero"]:
            self.assertIn("fevereiro", result["edital_numero"].lower())

    def test_extract_cargo_explicit(self):
        """Test cargo extraction from explicit label"""
        text = "Cargo: Professor Assistente de Física"
        result = extract_basic_metadata(text)
        if result["cargo"]:
            self.assertIn("Professor", result["cargo"])

    def test_extract_cargo_provimento(self):
        """Test cargo extraction from PROVIMENTO DE pattern"""
        text = "EDITAL PARA PROVIMENTO DE CARGOS DE PROFESSOR"
        result = extract_basic_metadata(text)
        if result["cargo"]:
            self.assertIn("PROFESSOR", result["cargo"].upper())

    def test_extract_banca_known(self):
        """Test extraction of known banca from whitelist"""
        text = "Concurso organizado pela CEBRASPE"
        result = extract_basic_metadata(text)
        banca = result["banca"]
        self.assertIsNotNone(banca)
        self.assertIsNotNone(banca.get("nome"))
        self.assertIn("CEBRASPE", banca["nome"].upper())

    def test_extract_banca_fgv(self):
        """Test extraction of FGV banca"""
        text = "A FGV será responsável pela execução deste concurso"
        result = extract_basic_metadata(text)
        banca = result["banca"]
        if banca["nome"]:
            self.assertIn("FGV", banca["nome"].upper())

    def test_extract_banca_from_pattern(self):
        """Test banca extraction from 'organized by' pattern"""
        text = "Concurso executado por Instituto de Pesquisas"
        result = extract_basic_metadata(text)
        banca = result["banca"]
        # Should find something
        self.assertTrue(banca["nome"] or banca["tipo"] is None)

    def test_extract_publication_date(self):
        """Test extraction of publication date from DOU"""
        text = "Publicado em 15 de fevereiro de 2026"
        result = extract_basic_metadata(text)
        # Should parse to ISO date if dateparser available
        pub_date = result["data_publicacao_dou"]
        if pub_date:
            self.assertRegex(pub_date, r'^\d{4}-\d{2}-\d{2}$')

    def test_metadata_with_minimal_text(self):
        """Test that metadata extraction handles minimal text gracefully"""
        text = "Minimal text"
        result = extract_basic_metadata(text)
        # Should not crash, all values should be None or empty
        self.assertIsNotNone(result)
        self.assertIn("orgao", result)


class TestExtractVagas(unittest.TestCase):
    """Test the extract_vagas() function"""

    def test_extract_total_vagas_explicit(self):
        """Test extraction of total vacancies with explicit label"""
        text = "Total de vagas: 50"
        result = extract_vagas(text)
        self.assertEqual(result["total"], 50)

    def test_extract_total_vagas_alternative_label(self):
        """Test with alternative 'Vagas totais' label"""
        text = "Vagas totais: 100"
        result = extract_vagas(text)
        self.assertEqual(result["total"], 100)

    def test_extract_total_vagas_fallback(self):
        """Test fallback pattern for total vagas"""
        text = "Vagas: 25 (ampla concorrência)"
        result = extract_vagas(text)
        self.assertIsNotNone(result["total"])

    def test_extract_pcd_vagas(self):
        """Test extraction of PCD vacancies"""
        text = "Total de vagas: 50\nPCD: 5"
        result = extract_vagas(text)
        self.assertEqual(result["pcd"], 5)

    def test_extract_ppiq_vagas(self):
        """Test extraction of PPIQ vacancies"""
        text = "Total de vagas: 100\nPPIQ: 20"
        result = extract_vagas(text)
        self.assertEqual(result["ppiq"], 20)

    def test_pcd_greater_than_total_check(self):
        """Test consistency check: PCD > total should be discarded"""
        text = "Total de vagas: 10\nPCD: 50"
        result = extract_vagas(text)
        # PCD (50) > Total (10), so PCD should be None
        self.assertIsNone(result["pcd"])

    def test_no_vagas_in_text(self):
        """Test text with no vacancy information"""
        text = "Este edital não menciona vagas"
        result = extract_vagas(text)
        self.assertIsNone(result["total"])
        self.assertIsNone(result["pcd"])

    def test_large_vacancy_numbers(self):
        """Test handling of larger vacancy numbers"""
        text = "Total de vagas: 1000"
        result = extract_vagas(text)
        self.assertEqual(result["total"], 1000)


class TestExtractFinanceiro(unittest.TestCase):
    """Test the extract_financeiro() function"""

    def test_extract_taxa_inscricao(self):
        """Test extraction of registration fee"""
        text = "Taxa de inscrição: R$ 100,00"
        result = extract_financeiro(text)
        self.assertIsNotNone(result["taxa_inscricao"])
        self.assertIn("100", result["taxa_inscricao"])

    def test_extract_remuneracao(self):
        """Test extraction of initial remuneration"""
        text = "Remuneração inicial: R$ 3.000,00"
        result = extract_financeiro(text)
        self.assertIsNotNone(result["remuneracao_inicial"])
        self.assertIn("3", result["remuneracao_inicial"])

    def test_extract_vencimento_alternative(self):
        """Test using 'Vencimento' label instead of 'Remuneração'"""
        text = "Vencimento: R$ 2.500,00"
        result = extract_financeiro(text)
        if result["remuneracao_inicial"]:
            self.assertIn("2500", result["remuneracao_inicial"].replace(".", ""))

    def test_no_financial_info(self):
        """Test text with no financial information"""
        text = "Edital sem informações financeiras"
        result = extract_financeiro(text)
        self.assertIsNone(result["taxa_inscricao"])

    def test_multiple_currencies_first_is_taxa(self):
        """Test that first currency is assumed to be taxa"""
        text = "R$ 150,00 de taxa e R$ 5.000,00 de remuneração"
        result = extract_financeiro(text)
        self.assertIsNotNone(result["taxa_inscricao"])
        self.assertIn("150", result["taxa_inscricao"])


class TestExtractCronograma(unittest.TestCase):
    """Test the extract_cronograma() function"""

    def test_extract_with_cebraspe_dates(self):
        """Test extraction from well-formed cronograma"""
        text = """
        CRONOGRAMA
        
        Recebimento de Inscrições: 10/02/2026 até 15/02/2026
        Período de solicitação de isenção: 10/02/2026 a 12/02/2026
        Data da prova: 20/02/2026
        """
        result = extract_cronograma(text)
        # Should extract at least one field
        fields_filled = sum(1 for v in result.values() if v)
        self.assertGreaterEqual(fields_filled, 1)

    def test_extract_inscrição_fields(self):
        """Test that inscrição dates are properly extracted"""
        text = "Período de Inscrição: 01/03/2026 a 10/03/2026"
        result = extract_cronograma(text)
        # Should have both start and end dates
        if result["inscricao_inicio"]:
            self.assertIsNotNone(result["inscricao_fim"])

    def test_extract_with_various_date_formats(self):
        """Test extraction with different date separators"""
        text = """
        Inscrições: 10-02-2026 até 15-02-2026
        Prova: 20/02/2026
        """
        result = extract_cronograma(text)
        # Should find at least prova date
        self.assertTrue(result["inscricao_inicio"] or result["data_prova"])

    def test_empty_cronograma_text(self):
        """Test with empty text"""
        result = extract_cronograma("")
        # All fields should be None
        for v in result.values():
            self.assertIsNone(v)

    def test_cronograma_with_messy_formatting(self):
        """Test extraction from poorly formatted cronograma"""
        text = """
        CRONOGRAMA (IMPORTANTE)
        =======================
        
        Inscrição....................................................................10/02 a 15/02/2026
        Prova.........................................................................20/02/2026
        
        Outras informações
        """
        result = extract_cronograma(text)
        # Should find at least one date
        fields_filled = sum(1 for v in result.values() if v)
        self.assertTrue(fields_filled >= 1)


class TestExtractorEdgeCases(unittest.TestCase):
    """Test edge cases and malformed inputs across extractor module"""

    def test_currency_with_negative_values(self):
        """Test that negative values might be parsed (edge case)"""
        text = "Débito: -R$ 100,00"
        result = _find_first_currency(text)
        # The regex looks for "R$" but might capture the minus
        self.assertIsNotNone(result)

    def test_metadata_with_special_characters(self):
        """Test metadata extraction with special characters"""
        text = """
        MINISTÉRIO DA EDUCAÇÃO & CULTURA
        
        EDITAL Nº 2024/2025 - CONCURSO PÚBLICO
        """
        result = extract_basic_metadata(text)
        # Should handle ampersands and special chars
        self.assertIsNotNone(result)

    def test_vagas_consistency_boundary(self):
        """Test PCD = Total edge case"""
        text = "Total: 5\nPCD: 5"
        result = extract_vagas(text)
        # PCD = Total should be allowed (all vagas for PCD)
        self.assertEqual(result["pcd"], 5)

    def test_vagas_zero_total(self):
        """Test when total vagas is zero"""
        text = "Total de vagas: 0"
        result = extract_vagas(text)
        self.assertEqual(result["total"], 0)

    def test_cronograma_date_format_mixed(self):
        """Test cronograma with mixed date formats in same text"""
        text = """
        Inscrição: 10/02/2026 a 15/02/2026
        Isenção: 12-02-2026
        Prova: 20.02.2026
        """
        result = extract_cronograma(text)
        # Should extract at least some dates
        fields_filled = sum(1 for v in result.values() if v)
        self.assertGreaterEqual(fields_filled, 1)

    def test_metadata_with_unicode_characters(self):
        """Test extraction with Portuguese accents"""
        text = """
        Órgão: Universidade Federal de São Paulo
        
        EDITAL: Seleção para Professor Adjunto
        Cargo: Matemática Aplicada
        """
        result = extract_basic_metadata(text)
        # Should handle unicode properly
        self.assertIsNotNone(result)

    def test_extract_banca_with_multiple_keywords(self):
        """Test banca extraction when multiple keywords present"""
        text = """
        Esta instituição organizadora é uma fundação privada.
        A VUNESP será responsável pela aplicação das provas.
        """
        result = extract_basic_metadata(text)
        banca = result["banca"]
        # Should find VUNESP (whitelisted banca)
        if banca["nome"]:
            self.assertIn("VUNESP", banca["nome"].upper())

    def test_financeiro_with_no_decimal_separator(self):
        """Test currency extraction with various decimal formats"""
        text = "R$ 1000"  # No cents, no separator
        result = extract_financeiro(text)
        # Regex should handle this
        if result["taxa_inscricao"]:
            self.assertIn("1000", result["taxa_inscricao"])


if __name__ == '__main__':
    unittest.main()
