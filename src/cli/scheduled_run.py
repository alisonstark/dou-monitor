import argparse
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run DOU monitor and notify when abertura concursos count reaches threshold."
    )
    parser.add_argument("--days", "-d", type=int, default=7, help="Lookback window in days")
    parser.add_argument(
        "--threshold",
        "-t",
        type=int,
        default=1,
        help="Send alert when abertura concursos count is >= threshold",
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


def send_email(subject: str, body: str) -> bool:
    host = os.getenv("DOU_SMTP_HOST", "")
    port = int(os.getenv("DOU_SMTP_PORT", "587"))
    user = os.getenv("DOU_SMTP_USER", "")
    password = os.getenv("DOU_SMTP_PASS", "")
    to_addr = os.getenv("DOU_NOTIFY_TO", "")
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


def send_webhook(subject: str, body: str) -> bool:
    webhook_url = os.getenv("DOU_WEBHOOK_URL", "")
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


def send_desktop(subject: str, body: str) -> bool:
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

    return_code, output = run_monitor(project_root=project_root, days=args.days)
    maybe_save_output(args.save_output, output)

    count = extract_count(output)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if return_code != 0:
        subject = "[DOU Monitor] Execution failed"
        body = f"Run at: {now}\nExit code: {return_code}\n\nOutput:\n{output[-5000:]}"
        notified = send_email(subject, body) or send_webhook(subject, body) or send_desktop(subject, body)
        print(output)
        print("Failure notification sent." if notified else "Execution failed and no notifier was configured.")
        return return_code

    print(output)

    if count is None:
        subject = "[DOU Monitor] Could not parse abertura count"
        body = f"Run at: {now}\n\nOutput snippet:\n{output[-5000:]}"
        notified = send_email(subject, body) or send_webhook(subject, body) or send_desktop(subject, body)
        print("Parse warning notification sent." if notified else "Could not parse count and no notifier was configured.")
        return 0

    if count >= args.threshold:
        subject = f"[DOU Monitor] {count} abertura concurso(s) found"
        body = (
            f"Run at: {now}\n"
            f"Threshold: {args.threshold}\n"
            f"Detected: {count}\n\n"
            "See command output for details."
        )
        notified = send_email(subject, body) or send_webhook(subject, body) or send_desktop(subject, body)
        print("Alert sent." if notified else "Alert condition met, but no notifier was configured.")
    else:
        print(f"No alert: detected {count}, threshold is {args.threshold}.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())