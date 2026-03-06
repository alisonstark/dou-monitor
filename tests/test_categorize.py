import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from web.dashboard_service import categorize_concursos  # noqa: E402


class TestCategorize(unittest.TestCase):
    def test_categorize_abertura_vs_outros(self):
        """Test that concursos are correctly categorized"""
        records = [
            {
                "id": "edital-de-abertura-concurso-1",
                "file_name": "edital-de-abertura-concurso-1.json",
                "orgao": "Universidade Federal X",
            },
            {
                "id": "edital-de-inicio-inscricoes",
                "file_name": "edital-de-inicio-inscricoes.json",
                "orgao": "Ministerio da Saude",
            },
            {
                "id": "edital-retificacao-concurso-y",
                "file_name": "edital-retificacao-concurso-y.json",
                "orgao": "Prefeitura de São Paulo",
            },
            {
                "id": "concurso-resultado-final",
                "file_name": "concurso-resultado-final.json",
                "orgao": "TRT 2a Região",
            },
        ]
        
        result = categorize_concursos(records)
        
        # First two should be abertura (abertura, inicio)
        self.assertEqual(len(result["abertura"]), 2)
        self.assertEqual(result["abertura"][0]["id"], "edital-de-abertura-concurso-1")
        self.assertEqual(result["abertura"][1]["id"], "edital-de-inicio-inscricoes")
        
        # Last two should be outros (retificacao, resultado)
        self.assertEqual(len(result["outros"]), 2)
        self.assertEqual(result["outros"][0]["id"], "edital-retificacao-concurso-y")
        self.assertEqual(result["outros"][1]["id"], "concurso-resultado-final")


if __name__ == "__main__":
    unittest.main()
