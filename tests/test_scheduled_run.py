import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cli.scheduled_run import load_dashboard_notification_settings  # noqa: E402


class TestScheduledRunDashboardConfig(unittest.TestCase):
    def test_load_dashboard_notification_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            config_path = data_dir / "dashboard_config.json"

            config = {
                "notifications": {
                    "threshold": 5,
                    "email_to": "alerta@example.com",
                    "webhook_url": "https://example.com/hook",
                    "desktop_enabled": False,
                }
            }
            config_path.write_text(json.dumps(config), encoding="utf-8")

            loaded = load_dashboard_notification_settings(root)
            self.assertEqual(loaded["threshold"], 5)
            self.assertEqual(loaded["email_to"], "alerta@example.com")
            self.assertEqual(loaded["webhook_url"], "https://example.com/hook")
            self.assertFalse(loaded["desktop_enabled"])


if __name__ == "__main__":
    unittest.main()
