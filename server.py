#!/usr/bin/env python3
"""Web service for a Notion "Send webhook" button: sets the clicked card's cover.

Anyone can connect their own Notion through the home page (Notion's "Connect" screen,
no keys to copy). They get a personal button URL that only works for the pages they shared.
That URL carries their access token encrypted with SECRET_KEY, so nothing is stored here.

Environment variables:
  NOTION_CLIENT_ID      from your public Notion integration (OAuth client ID)
  NOTION_CLIENT_SECRET  from your public Notion integration (OAuth client secret)
  SECRET_KEY            any long random text you make up; changing it breaks existing buttons
  BASE_URL              this service's address (Render sets RENDER_EXTERNAL_URL, used if missing)
  NOTION_TOKEN, WEBHOOK_KEY   optional: your own internal integration, used when ?key=WEBHOOK_KEY
  PORT                  set automatically by most hosts (default 8000)
"""
import base64, hashlib, hmac, html, json, os, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlencode, urlparse, parse_qs

import requests
from cryptography.fernet import Fernet, InvalidToken

from hanzi_covers import Notion, font

CLIENT_ID = os.environ.get("NOTION_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("NOTION_CLIENT_SECRET", "")
BASE_URL = (os.environ.get("BASE_URL") or os.environ.get("RENDER_EXTERNAL_URL", "http://localhost:8000")).rstrip("/")
REDIRECT_URI = BASE_URL + "/callback"
OWNER_KEY = os.environ.get("WEBHOOK_KEY", "")
OWNER_TOKEN = os.environ.get("NOTION_TOKEN", "")
fernet = Fernet(base64.urlsafe_b64encode(hashlib.sha256(os.environ["SECRET_KEY"].encode()).digest()))
font(10)  # download the font once at startup

PAGE = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Hanzi covers</title><style>body{{font-family:system-ui,sans-serif;max-width:640px;margin:40px auto;padding:0 16px;line-height:1.5}}
a.btn{{display:inline-block;background:#B22222;color:#fff;padding:10px 18px;border-radius:6px;text-decoration:none}}
code{{display:block;word-break:break-all;background:#f3f3f3;padding:10px;border-radius:6px}}</style></head><body>{}</body></html>"""

HOME = """<h1>汉字 Hanzi covers</h1>
<p>Adds a cover image of the character to each flashcard in your Notion database when you click its button.</p>
<p><a class="btn" href="{}">Connect your Notion</a></p>
<p>On the next screen, choose your flashcard database. You'll then get your personal button URL.</p>"""

DONE = """<h1>Connected ✓</h1>
<p>Your personal button URL:</p><code>{}</code>
<ol><li>Copy the URL above.</li>
<li>In your flashcard database, open the <b>Make cover</b> button property (or add a Button property).</li>
<li>Set its action to <b>Send webhook</b> and paste the URL. Save.</li></ol>
<p>Keep this URL to yourself: anyone with it can change covers on the pages you shared.
To revoke access, remove the connection in Notion under Settings › Connections.</p>"""


def handle(token, page_id):
    try:
        nt = Notion(token)
        hanzi = nt.cover_page(nt.page(page_id))
        print(f"✓ {hanzi}" if hanzi else f"- {page_id}: empty Hanzi field", flush=True)
    except Exception as e:
        print(f"✗ {page_id}: {e}", flush=True)


def token_for(key):
    if OWNER_KEY and OWNER_TOKEN and hmac.compare_digest(key, OWNER_KEY):
        return OWNER_TOKEN
    try:
        return fernet.decrypt(key.encode()).decode()
    except (InvalidToken, ValueError):
        return None


class Handler(BaseHTTPRequestHandler):
    def send(self, code, body=""):
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(PAGE.format(body).encode())

    def do_GET(self):
        url = urlparse(self.path)
        q = parse_qs(url.query)
        if url.path == "/callback":
            if "code" not in q:
                return self.send(400, "<p>Connection cancelled. <a href='/'>Try again</a>.</p>")
            r = requests.post("https://api.notion.com/v1/oauth/token", auth=(CLIENT_ID, CLIENT_SECRET),
                              json={"grant_type": "authorization_code", "code": q["code"][0],
                                    "redirect_uri": REDIRECT_URI}, timeout=30)
            if not r.ok:
                print("OAuth error:", r.text, flush=True)
                return self.send(400, "<p>Notion didn't accept the connection. <a href='/'>Try again</a>.</p>")
            key = fernet.encrypt(r.json()["access_token"].encode()).decode()
            return self.send(200, DONE.format(html.escape(f"{BASE_URL}/?{urlencode({'key': key})}")))
        auth = "https://api.notion.com/v1/oauth/authorize?" + urlencode(
            {"client_id": CLIENT_ID, "response_type": "code", "owner": "user", "redirect_uri": REDIRECT_URI})
        self.send(200, HOME.format(html.escape(auth)))

    def do_POST(self):
        token = token_for(parse_qs(urlparse(self.path).query).get("key", [""])[0])
        if not token:
            return self.send(403)
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        page_id = body.get("data", body).get("id")  # Notion sends the clicked page under "data"
        self.send(200 if page_id else 400)
        if page_id:
            # Reply to Notion right away; draw and upload in the background.
            threading.Thread(target=handle, args=(token, page_id)).start()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"Listening on port {port}", flush=True)
    ThreadingHTTPServer(("", port), Handler).serve_forever()
