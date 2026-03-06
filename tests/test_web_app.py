import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from web.app import create_app  # noqa: E402


def _login_test_user(client, app):
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
        session["session_boot_id"] = app.config.get("SERVER_BOOT_ID")


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
            app.config["TESTING"] = True
            app.config["WTF_CSRF_ENABLED"] = False
            client = app.test_client()
            _login_test_user(client, app)

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
            app.config["TESTING"] = True
            app.config["WTF_CSRF_ENABLED"] = False
            client = app.test_client()
            _login_test_user(client, app)

            # Test that POST to /run/manual redirects (default behavior)
            # We don't test actual monitoring since it requires network access
            response = client.post("/run/manual", data={"days": "7", "export_pdf": "off"}, follow_redirects=False)
            
            # Should redirect back to index
            self.assertEqual(response.status_code, 302)
            self.assertTrue("/" in response.location)

    def test_manual_review_route_applies_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summaries_dir = root / "summaries"
            summaries_dir.mkdir(parents=True, exist_ok=True)
            config_path = root / "dashboard_config.json"

            sample = {
                "metadata": {
                    "orgao": "Ministerio X",
                    "edital_numero": "10/2026",
                    "cargo": "Analista",
                    "banca": {"nome": "Banca Antiga"},
                },
                "vagas": {"total": 1},
                "financeiro": {"taxa_inscricao": "R$ 50,00"},
                "cronograma": {"data_prova": "2026-06-01"},
            }
            file_name = "edital-abertura-teste.json"
            (summaries_dir / file_name).write_text(json.dumps(sample), encoding="utf-8")

            app = create_app(summaries_dir=summaries_dir, config_path=config_path)
            app.config["TESTING"] = True
            app.config["WTF_CSRF_ENABLED"] = False
            client = app.test_client()
            _login_test_user(client, app)

            html_resp = client.get(f"/?edit={file_name}")
            self.assertEqual(html_resp.status_code, 200)
            self.assertIn("Revisao Manual (MIT)", html_resp.get_data(as_text=True))

            post_resp = client.post(
                "/review/manual",
                data={
                    "file_name": file_name,
                    "reviewer": "teste-web",
                    "next_query": "q=analista",
                    "orgao": "Ministerio Y",
                    "edital_numero": "11/2026",
                    "cargo": "Analista Senior",
                    "banca": "FCC",
                    "vagas_total": "3",
                    "taxa_inscricao": "R$ 80,00",
                    "data_prova": "2026-07-10",
                },
                follow_redirects=False,
            )
            self.assertEqual(post_resp.status_code, 302)
            self.assertTrue("q=analista" in post_resp.location)

            updated = json.loads((summaries_dir / file_name).read_text(encoding="utf-8"))
            self.assertEqual(updated["metadata"]["orgao"], "Ministerio Y")
            self.assertEqual(updated["metadata"]["cargo"], "Analista Senior")
            self.assertEqual(updated["vagas"]["total"], 3)
            self.assertEqual(updated["_review"]["reviewer"], "teste-web")


if __name__ == "__main__":
    unittest.main()
