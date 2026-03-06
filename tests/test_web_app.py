import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from web.app import create_app  # noqa: E402


class TestWebApp(unittest.TestCase):
    def test_dashboard_and_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summaries_dir = root / "summaries"
            summaries_dir.mkdir(parents=True, exist_ok=True)
            config_path = root / "dashboard_config.json"

            sample = {
                "metadata": {
                    "orgao": "Universidade Federal X",
                    "edital_numero": "11/2026",
                    "cargo": "Professor",
                    "banca": {"nome": "FCC"},
                },
                "vagas": {"total": 4},
                "financeiro": {"taxa_inscricao": "R$ 120,00"},
                "cronograma": {"data_prova": "2026-06-01"},
            }
            (summaries_dir / "item.json").write_text(json.dumps(sample), encoding="utf-8")

            app = create_app(summaries_dir=summaries_dir, config_path=config_path)
            client = app.test_client()

            html_resp = client.get("/?q=prof&sort_by=orgao&sort_dir=asc&page=1&page_size=10")
            self.assertEqual(html_resp.status_code, 200)

            api_resp = client.get("/api/concursos?cargo=Professor&page=1&page_size=5")
            self.assertEqual(api_resp.status_code, 200)

            payload = api_resp.get_json()
            self.assertEqual(payload["pagination"]["total"], 1)
            self.assertEqual(payload["items"][0]["cargo"], "Professor")

    def test_manual_run_route_exists(self):
        """Test that manual run route responds (without executing actual monitoring)"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summaries_dir = root / "summaries"
            summaries_dir.mkdir(parents=True, exist_ok=True)
            config_path = root / "dashboard_config.json"

            app = create_app(summaries_dir=summaries_dir, config_path=config_path)
            client = app.test_client()

            # Test that POST to /run/manual redirects (default behavior)
            # We don't test actual monitoring since it requires network access
            response = client.post("/run/manual", data={"days": "7", "export_pdf": "off"}, follow_redirects=False)
            
            # Should redirect back to index
            self.assertEqual(response.status_code, 302)
            self.assertTrue("/" in response.location)


if __name__ == "__main__":
    unittest.main()
