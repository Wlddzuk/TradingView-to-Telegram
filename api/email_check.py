# api/email_check.py
from http.server import BaseHTTPRequestHandler
import json, os

REQUIRED_KEYS = [
    "GMAIL_EMAIL",
    "GMAIL_APP_PASSWORD",
    "GMAIL_FOLDER_NAME",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID_DEFAULT",
    "TV_SHARED_SECRET",
]

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        missing = [k for k in REQUIRED_KEYS if not os.environ.get(k)]
        payload = {
            "ok": len(missing) == 0,
            "missing": missing,
            "folder": os.environ.get("GMAIL_FOLDER_NAME"),
        }
        body = json.dumps(payload).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
