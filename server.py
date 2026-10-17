#!/usr/bin/env python3
"""Tiny web service for a Notion "Send webhook" button: sets the clicked card's cover.

Environment variables:
  NOTION_TOKEN    your integration secret (ntn_...)
  WEBHOOK_KEY     any long random word you choose; the button URL must end in ?key=<WEBHOOK_KEY>
  PORT            set automatically by most hosts (default 8000)
"""
import hmac, json, os, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from hanzi_covers import Notion, font

KEY = os.environ["WEBHOOK_KEY"]
nt = Notion(os.environ["NOTION_TOKEN"])
font(10)  # download the font once at startup


def handle(page_id):
    try:
        hanzi = nt.cover_page(nt.page(page_id))
        print(f"✓ {hanzi}" if hanzi else f"- {page_id}: empty Hanzi field", flush=True)
    except Exception as e:
        print(f"✗ {page_id}: {e}", flush=True)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # health check, and lets you open the URL in a browser to wake the service
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Hanzi cover service is running.")

    def do_POST(self):
        key = parse_qs(urlparse(self.path).query).get("key", [""])[0]
        if not hmac.compare_digest(key, KEY):
            self.send_response(403)
            self.end_headers()
            return
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        page = body.get("data", body)  # Notion sends the clicked page under "data"
        page_id = page.get("id")
        self.send_response(200 if page_id else 400)
        self.end_headers()
        if page_id:
            # Reply to Notion right away; draw and upload in the background.
            threading.Thread(target=handle, args=(page_id,)).start()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"Listening on port {port}", flush=True)
    ThreadingHTTPServer(("", port), Handler).serve_forever()
