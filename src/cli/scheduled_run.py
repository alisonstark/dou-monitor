import argparse
import json
import os
import re
import shutil
import smtplib
import subprocess
import sys
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from urllib import error, request


COUNT_PATTERN = re.compile(r"Total abertura concursos \(keywords: .*?\):\s*(\d+)")


DEFAULT_DASHBOARD_CONFIG = {
    "notifications": {
        "threshold": 1,
        "email_to": "",
        "webhook_url": "",
        "desktop_enabled": True,
    }
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Doumon and notify when abertura concursos count reaches threshold."
    )
    parser.add_argument("--days", "-d", type=int, default=7, help="Lookback window in days")
    parser.add_argument(
        "--threshold",
        "-t",
        type=int,
        default=None,
        help="Send alert when abertura concursos count is >= threshold (defaults to dashboard setting)",
    )
    parser.add_argument(
        "--save-output",
        default="",
        help="Optional path to save full command output",
    )
    return parser.parse_args()


def run_monitor(project_root: Path, days: int) -> tuple[int, str]:
    main_py = project_root / "src" / "main.py"
    cmd = [sys.executable, str(main_py), "-d", str(days)]
    process = subprocess.run(
        cmd,
        cwd=str(project_root),
        capture_output=True,
        text=True,
        check=False,
    )
    output = (process.stdout or "") + ("\n" + process.stderr if process.stderr else "")
    return process.returncode, output


def extract_count(output: str) -> int | None:
    match = COUNT_PATTERN.search(output)
    if not match:
        return None
    return int(match.group(1))


def load_dashboard_notification_settings(project_root: Path) -> dict:
    config_path = project_root / "data" / "dashboard_config.json"
    settings = DEFAULT_DASHBOARD_CONFIG["notifications"].copy()
    if not config_path.exists():
        return settings

    try:
        content = json.loads(config_path.read_text(encoding="utf-8"))
        notifications = content.get("notifications", {}) if isinstance(content, dict) else {}
        settings["threshold"] = int(notifications.get("threshold", settings["threshold"]))
        settings["email_to"] = str(notifications.get("email_to", settings["email_to"])).strip()
        settings["webhook_url"] = str(notifications.get("webhook_url", settings["webhook_url"])).strip()
        settings["desktop_enabled"] = bool(notifications.get("desktop_enabled", settings["desktop_enabled"]))
    except Exception:
        pass

    return settings


def send_email(subject: str, body: str, fallback_email_to: str = "") -> bool:
    host = os.getenv("DOU_SMTP_HOST", "")
    port = int(os.getenv("DOU_SMTP_PORT", "587"))
    user = os.getenv("DOU_SMTP_USER", "")
    password = os.getenv("DOU_SMTP_PASS", "")
    to_addr = os.getenv("DOU_NOTIFY_TO", fallback_email_to)
    from_addr = os.getenv("DOU_NOTIFY_FROM", user)

    if not all([host, user, password, to_addr, from_addr]):
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.set_content(body)

    try:
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(user, password)
            smtp.send_message(msg)
        return True
    except Exception as exc:
        print(f"Email notification failed: {exc}")
        return False


def send_webhook(subject: str, body: str, fallback_webhook_url: str = "") -> bool:
    webhook_url = os.getenv("DOU_WEBHOOK_URL", fallback_webhook_url)
    if not webhook_url:
        return False

    payload = f"{subject}\n\n{body}".encode("utf-8")
    req = request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "text/plain; charset=utf-8"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=30):
            return True
    except error.URLError as exc:
        print(f"Webhook notification failed: {exc}")
        return False


def send_desktop(subject: str, body: str, enabled: bool = True) -> bool:
    if not enabled:
        return False
    if shutil.which("notify-send") is None:
        return False

    try:
        subprocess.run(["notify-send", subject, body], check=False)
        return True
    except Exception as exc:
        print(f"Desktop notification failed: {exc}")
        return False


def maybe_save_output(path_value: str, output: str) -> None:
    if not path_value:
        return

    output_path = Path(path_value).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(output, encoding="utf-8")


def main() -> int:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[2]
    dashboard_notifications = load_dashboard_notification_settings(project_root)
    threshold = args.threshold if args.threshold is not None else int(dashboard_notifications["threshold"])

    return_code, output = run_monitor(project_root=project_root, days=args.days)
    maybe_save_output(args.save_output, output)

    count = extract_count(output)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def notify_any(subject: str, body: str) -> bool:
        return (
            send_email(subject, body, fallback_email_to=dashboard_notifications["email_to"])
            or send_webhook(subject, body, fallback_webhook_url=dashboard_notifications["webhook_url"])
            or send_desktop(subject, body, enabled=dashboard_notifications["desktop_enabled"])
        )

    if return_code != 0:
        subject = "[Doumon] Execution failed"
        body = f"Run at: {now}\nExit code: {return_code}\n\nOutput:\n{output[-5000:]}"
        notified = notify_any(subject, body)
        print(output)
        print("Failure notification sent." if notified else "Execution failed and no notifier was configured.")
        return return_code

    print(output)

    if count is None:
        subject = "[Doumon] Could not parse abertura count"
        body = f"Run at: {now}\n\nOutput snippet:\n{output[-5000:]}"
        notified = notify_any(subject, body)
        print("Parse warning notification sent." if notified else "Could not parse count and no notifier was configured.")
        return 0

    if count >= threshold:
        subject = f"[Doumon] {count} abertura concurso(s) found"
        body = (
            f"Run at: {now}\n"
            f"Threshold: {threshold}\n"
            f"Detected: {count}\n\n"
            "See command output for details."
        )
        notified = notify_any(subject, body)
        print("Alert sent." if notified else "Alert condition met, but no notifier was configured.")
    else:
        print(f"No alert: detected {count}, threshold is {threshold}.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())