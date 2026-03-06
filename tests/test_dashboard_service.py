import sys
import tempfile
import unittest
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from web.dashboard_service import (  # noqa: E402
    apply_manual_review,
    filter_summaries,
    load_dashboard_config,
    load_summaries,
    paginate_summaries,
    save_dashboard_config,
    sort_summaries,
    summarize_metrics,
)


class TestDashboardService(unittest.TestCase):
    def test_config_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "dashboard_config.json"
            config = load_dashboard_config(config_path)
            self.assertEqual(config["notifications"]["threshold"], 1)

            config["notifications"]["threshold"] = 3
            config["filters"]["keywords"] = ["abertura", "nomeacao"]
            save_dashboard_config(config_path, config)

            reloaded = load_dashboard_config(config_path)
            self.assertEqual(reloaded["notifications"]["threshold"], 3)
            self.assertIn("nomeacao", reloaded["filters"]["keywords"])

    def test_load_and_filter_summaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            summaries_dir = Path(tmp)
            content = """{
              \"metadata\": {
                \"orgao\": \"Universidade Federal X\",
                \"edital_numero\": \"12/2026\",
                \"cargo\": \"Professor\",
                \"banca\": {\"nome\": \"FCC\"}
              },
              \"vagas\": {\"total\": 8},
              \"financeiro\": {\"taxa_inscricao\": \"R$ 100,00\"},
              \"cronograma\": {\"data_prova\": \"2026-05-12\"}
            }"""
            (summaries_dir / "amostra.json").write_text(content, encoding="utf-8")

            records = load_summaries(summaries_dir)
            self.assertEqual(len(records), 1)

            filtered = filter_summaries(records, {"cargo": "prof"})
            self.assertEqual(len(filtered), 1)

            filtered_empty = filter_summaries(records, {"banca": "CEBRASPE"})
            self.assertEqual(len(filtered_empty), 0)

            by_date = filter_summaries(
                records,
                {
                    "date_from": "2026-05-01",
                    "date_to": "2026-05-30",
                },
            )
            self.assertEqual(len(by_date), 1)

    def test_metrics(self):
        records = [
            {"data_prova": "2026-01-02", "banca": "FCC", "vagas_total": 2},
            {"data_prova": "", "banca": "", "vagas_total": None},
        ]
        metrics = summarize_metrics(records)
        self.assertEqual(metrics["total"], 2)
        self.assertEqual(metrics["with_prova"], 1)
        self.assertEqual(metrics["with_banca"], 1)
        self.assertEqual(metrics["with_vagas"], 1)

    def test_sort_and_paginate(self):
        records = [
            {"orgao": "B", "data_prova": "2026-03-01", "vagas_total": 1},
            {"orgao": "A", "data_prova": "2026-01-01", "vagas_total": 3},
            {"orgao": "C", "data_prova": "", "vagas_total": None},
        ]

        sorted_records = sort_summaries(records, "orgao", "asc")
        self.assertEqual(sorted_records[0]["orgao"], "A")

        sorted_vagas = sort_summaries(records, "vagas_total", "desc")
        self.assertEqual(sorted_vagas[0]["vagas_total"], 3)

        page_items, meta = paginate_summaries(sorted_records, page=2, page_size=2)
        self.assertEqual(len(page_items), 1)
        self.assertEqual(meta["total_pages"], 2)
        self.assertEqual(meta["page"], 2)

    def test_apply_manual_review_updates_file_and_creates_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summaries_dir = root / "summaries"
            backups_dir = root / "backups"
            reviewed_dir = root / "reviewed_examples"
            summaries_dir.mkdir(parents=True, exist_ok=True)

            summary_payload = {
                "metadata": {
                    "orgao": "Universidade Federal X",
                    "edital_numero": "12/2026",
                    "cargo": "Professor",
                    "banca": {"nome": "Desconhecida"},
                },
                "vagas": {"total": 2},
                "financeiro": {"taxa_inscricao": "R$ 100,00"},
                "cronograma": {"data_prova": "2026-05-12"},
            }
            file_name = "edital-abertura-x.json"
            (summaries_dir / file_name).write_text(json.dumps(summary_payload), encoding="utf-8")

            result = apply_manual_review(
                summaries_dir=summaries_dir,
                backup_dir=backups_dir,
                reviewed_examples_dir=reviewed_dir,
                file_name=file_name,
                updates={
                    "orgao": "Universidade Federal Y",
                    "edital_numero": "99/2026",
                    "cargo": "Professor Adjunto",
                    "banca": "FCC",
                    "vagas_total": "5",
                    "taxa_inscricao": "R$ 150,00",
                    "data_prova": "2026-08-01",
                },
                reviewer="teste-mit",
            )

            self.assertTrue(result["success"])
            self.assertGreater(len(result["changed_fields"]), 0)

            updated = json.loads((summaries_dir / file_name).read_text(encoding="utf-8"))
            self.assertEqual(updated["metadata"]["orgao"], "Universidade Federal Y")
            self.assertEqual(updated["metadata"]["banca"]["nome"], "FCC")
            self.assertEqual(updated["metadata"]["banca"]["tipo"], "manual")
            self.assertEqual(updated["vagas"]["total"], 5)
            self.assertEqual(updated["_review"]["reviewer"], "teste-mit")

            backup_files = list(backups_dir.glob("*.bak"))
            reviewed_files = list(reviewed_dir.glob("*.json"))
            self.assertEqual(len(backup_files), 1)
            self.assertEqual(len(reviewed_files), 1)


if __name__ == "__main__":
    unittest.main()
