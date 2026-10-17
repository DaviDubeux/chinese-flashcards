#!/usr/bin/env python3
"""Hanzi cover service.

  GET  /cover/<hanzi>.png   Public image link for anyone's Notion cover. No Notion access, no keys.
                            The template builds this link with a formula from the Hanzi field.
  POST /?key=WEBHOOK_KEY    Your Notion automation (Send webhook): sets the card's
                            cover and fills its Pinyin and HSK fields.

Environment variables:
  NOTION_TOKEN   your Hanzi Cover integration secret (ntn_...), for your own button
  WEBHOOK_KEY    any long random word you choose; your button URL ends in ?key=<WEBHOOK_KEY>
  PORT           set automatically by most hosts (default 8000)
"""
import hmac, json, os, threading
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse, parse_qs

from hanzi_covers import Notion, font, hsk_words, render

KEY = os.environ.get("WEBHOOK_KEY", "")
TOKEN = os.environ.get("NOTION_TOKEN", "")
MAX_CHARS = 8  # longest word drawn on a public cover
font(10)  # download the font and word list once at startup
hsk_words()


@lru_cache(maxsize=2000)
def cover_png(hanzi):
    return render(hanzi)


def handle(page_id):
    try:
        nt = Notion(TOKEN)
        page = nt.page(page_id)
        filled = nt.fill_fields(page)
        hanzi = nt.cover_page(page)
        print(f"✓ {hanzi} " + " | ".join(filled.values()) if hanzi else f"- {page_id}: empty Hanzi field",
              flush=True)
    except Exception as e:
        print(f"✗ {page_id}: {e}", flush=True)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path.startswith("/cover/"):
            hanzi = path[len("/cover/"):].removesuffix(".png").strip()
            if not hanzi or len(hanzi) > MAX_CHARS:
                self.send_response(404)
                self.end_headers()
                return
            png = cover_png(hanzi)
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(png)))
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
            self.end_headers()
            self.wfile.write(png)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write("Hanzi cover service is running. Example: /cover/学.png".encode())

    def do_POST(self):
        key = parse_qs(urlparse(self.path).query).get("key", [""])[0]
        if not (KEY and TOKEN and hmac.compare_digest(key, KEY)):
            self.send_response(403)
            self.end_headers()
            return
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        page_id = body.get("data", body).get("id")  # Notion sends the clicked page under "data"
        self.send_response(200 if page_id else 400)
        self.end_headers()
        if page_id:
            # Reply to Notion right away; draw and upload in the background.
            threading.Thread(target=handle, args=(page_id,)).start()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"Listening on port {port}", flush=True)
    ThreadingHTTPServer(("", port), Handler).serve_forever()
