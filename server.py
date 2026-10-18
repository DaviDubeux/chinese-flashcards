#!/usr/bin/env python3
"""Hanzi cover service.

  GET  /cover/<hanzi>.png   Public image link for anyone's Notion cover. No Notion access, no keys.
                            The template builds this link with a formula from the Hanzi field.
  POST /?key=WEBHOOK_KEY    Your Notion automation (Send webhook): sets the card's
                            cover and fills its Pinyin and HSK fields.
  POST /random?key=WEBHOOK_KEY&prop=Revisar&n=10
                            Your Notion button (Send webhook): picks n random cards that don't
                            have the value yet and sets prop on them. Options:
                              value=...  what to set (default: checked / today / "true")
                              reset=1    first clear prop on every card that has it
                              db=...     database id (default: NOTION_DATABASE_ID, else the
                                         database of the page the button is on)

Environment variables:
  NOTION_TOKEN   your Hanzi Cover integration secret (ntn_...), for your own button
  WEBHOOK_KEY    any long random word you choose; your button URL ends in ?key=<WEBHOOK_KEY>
  NOTION_DATABASE_ID  optional, the flashcards database for /random
  PORT           set automatically by most hosts (default 8000)
"""
import datetime, hmac, json, os, random, threading
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse, parse_qs

from hanzi_covers import Notion, font, hsk_words, plain, prop_value, render

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


def set_value(prop, value):
    """Notion payload that sets prop to value ("" clears it)."""
    kind = prop["type"]
    if kind == "checkbox":
        return {"checkbox": value.lower() in ("true", "1", "yes", "on")} if value else {"checkbox": False}
    if kind == "date":
        when = datetime.date.today().isoformat() if value.lower() in ("", "today") else value
        return {"date": {"start": when}} if value != "-" else {"date": None}
    if kind == "status":
        return {"status": {"name": value}}
    if not value:
        return {kind: [] if kind in ("rich_text", "title", "multi_select") else None}
    return prop_value(prop, value)


def current(prop):
    """A property's value as plain text, for comparing."""
    kind, v = prop["type"], prop.get(prop["type"])
    if kind == "checkbox":
        return "true" if v else ""
    if kind in ("select", "status"):
        return (v or {}).get("name", "")
    if kind == "multi_select":
        return ",".join(o["name"] for o in v)
    if kind == "date":
        return (v or {}).get("start", "")
    if kind == "number":
        return "" if v is None else str(v)
    return plain(prop)


def pick_random(db, name, n, value, reset):
    try:
        nt = Notion(TOKEN)
        pages = list(nt.pages(db))
        if not pages or name not in pages[0]["properties"]:
            print(f"✗ random: no property named '{name}'", flush=True)
            return
        if value is None:  # default: checked, today, or the word "true"
            value = {"checkbox": "true", "date": "today"}.get(pages[0]["properties"][name]["type"], "true")
        target = set_value(pages[0]["properties"][name], value)
        kind = next(iter(target))
        want = value if kind in ("rich_text", "title") else current({"type": kind, **target})
        cleared = 0
        if reset:
            for p in pages:
                prop = p["properties"][name]
                if current(prop) and prop["type"] != "status":  # a status can't be emptied
                    nt.call("PATCH", f"/pages/{p['id']}", json={"properties": {name: set_value(prop, "")}})
                    p["properties"][name] = {"type": prop["type"], **set_value(prop, "")}
                    cleared += 1
        pool = [p for p in pages if current(p["properties"][name]) != want]
        chosen = random.sample(pool, min(n, len(pool)))
        for p in chosen:
            nt.call("PATCH", f"/pages/{p['id']}", json={"properties": {name: target}})
        words = [plain(p["properties"].get("Hanzi")) or p["id"] for p in chosen]
        print(f"✓ random: {name}={value} on {len(chosen)} cards ({cleared} cleared): " + " ".join(words),
              flush=True)
    except Exception as e:
        print(f"✗ random: {e}", flush=True)


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
        url = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        if not (KEY and TOKEN and hmac.compare_digest(q.get("key", ""), KEY)):
            self.send_response(403)
            self.end_headers()
            return
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        if url.path.rstrip("/") == "/random":
            parent = body.get("data", body).get("parent", {})
            db = q.get("db") or os.environ.get("NOTION_DATABASE_ID") or parent.get("database_id")
            ok = bool(db and q.get("prop"))
            self.send_response(200 if ok else 400)
            self.end_headers()
            if ok:
                threading.Thread(target=pick_random, args=(db, q["prop"], int(q.get("n", 10)),
                                                           q.get("value"), q.get("reset") == "1")).start()
            return
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
