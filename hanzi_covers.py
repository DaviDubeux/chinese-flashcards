#!/usr/bin/env python3
"""Render a cover image from each Notion entry's Hanzi field and set it as the page cover.

Setup:
  1. Create an integration at https://www.notion.so/profile/integrations and copy its token.
  2. Open your flashcard database in Notion > ••• > Connections > add the integration.
  3. pip install pillow requests
  4. export NOTION_TOKEN=secret_...   NOTION_DATABASE_ID=<32-char id from the database URL>
  5. python3 hanzi_covers.py            # only entries without a cover
     python3 hanzi_covers.py --force    # redo every entry
     python3 hanzi_covers.py --preview 你好   # just write preview.png, no Notion calls

Property names are set below (HANZI_PROP, PINYIN_PROP). Pinyin is optional.
The font is Noto Serif SC (SIL Open Font License), so the images are free to share.
"""
import io, os, sys, time
import requests
from PIL import Image, ImageDraw, ImageFont

HANZI_PROP = "Hanzi"     # title or text property holding the character(s)
PINYIN_PROP = "Pinyin"   # optional text property; ignored if missing
SHOW_PINYIN = False      # set to True to print pinyin under the characters
COVER_PROP = "Cover"     # optional Files & media property; also filled with the image if it exists
WIDTH, HEIGHT = 1500, 600  # Notion's cover size (shown center-cropped)
BG, FG, SUB = "#FBF7EF", "#B22222", "#555555"

FONT_URL = "https://raw.githubusercontent.com/notofonts/noto-cjk/main/Serif/SubsetOTF/SC/NotoSerifSC-Bold.otf"
FONT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "NotoSerifSC-Bold.otf")
API = "https://api.notion.com/v1"


def font(size):
    if not os.path.exists(FONT_PATH):
        print("Downloading Noto Serif SC font...")
        # requests ships its own certificates (certifi), unlike urllib on some Macs.
        r = requests.get(FONT_URL, timeout=120)
        r.raise_for_status()
        with open(FONT_PATH, "wb") as fh:
            fh.write(r.content)
    return ImageFont.truetype(FONT_PATH, size)


def render(hanzi, pinyin=""):
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    d = ImageDraw.Draw(img)
    # Keep glyphs small enough to survive Notion cropping the top and bottom on wide screens.
    size = 300 if pinyin else 360
    while True:
        f = font(size)
        l, t, r, b = d.textbbox((0, 0), hanzi, font=f)
        if r - l <= WIDTH * 0.7 or size <= 60:
            break
        size -= 20
    text_h = b - t
    pin_f = font(64)
    pin_h = 90 if pinyin else 0
    top = (HEIGHT - text_h - pin_h) / 2 - t
    d.text(((WIDTH - (r - l)) / 2 - l, top), hanzi, font=f, fill=FG)
    if pinyin:
        pl, pt, pr, pb = d.textbbox((0, 0), pinyin, font=pin_f)
        d.text(((WIDTH - (pr - pl)) / 2 - pl, top + b + 30), pinyin, font=pin_f, fill=SUB)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def plain(prop):
    if not prop:
        return ""
    parts = prop.get(prop["type"], [])
    return "".join(p.get("plain_text", "") for p in parts).strip() if isinstance(parts, list) else ""


class Notion:
    def __init__(self, token):
        self.h = {"Authorization": f"Bearer {token}", "Notion-Version": "2022-06-28"}

    def call(self, method, path, **kw):
        for _ in range(5):
            r = requests.request(method, API + path, headers=self.h, **kw)
            if r.status_code == 429:  # rate limited
                time.sleep(float(r.headers.get("Retry-After", 1)))
                continue
            r.raise_for_status()
            return r.json()
        r.raise_for_status()

    def pages(self, db):
        body = {"page_size": 100}
        while True:
            res = self.call("POST", f"/databases/{db}/query", json=body)
            yield from res["results"]
            if not res.get("has_more"):
                return
            body["start_cursor"] = res["next_cursor"]

    def page(self, page_id):
        return self.call("GET", f"/pages/{page_id}")

    def cover_page(self, page):
        """Render and set the cover for one page. Returns the hanzi, or None if the field is empty."""
        props = page["properties"]
        hanzi = plain(props.get(HANZI_PROP))
        if not hanzi:
            return None
        pinyin = plain(props.get(PINYIN_PROP)) if SHOW_PINYIN else ""
        self.set_cover(page, render(hanzi, pinyin), f"{hanzi}.png")
        return hanzi

    def set_cover(self, page, png, name):
        up = self.call("POST", "/file_uploads", json={"filename": name, "content_type": "image/png"})
        self.call("POST", f"/file_uploads/{up['id']}/send", files={"file": (name, png, "image/png")})
        # Set the page cover (the banner at the top of the page / gallery card preview).
        self.call("PATCH", f"/pages/{page['id']}",
                  json={"cover": {"type": "file_upload", "file_upload": {"id": up["id"]}}})
        # Also fill a Files & media column, if the database has one named COVER_PROP.
        if page["properties"].get(COVER_PROP, {}).get("type") == "files":
            up2 = self.call("POST", "/file_uploads", json={"filename": name, "content_type": "image/png"})
            self.call("POST", f"/file_uploads/{up2['id']}/send", files={"file": (name, png, "image/png")})
            self.call("PATCH", f"/pages/{page['id']}", json={"properties": {COVER_PROP: {"files": [
                {"type": "file_upload", "file_upload": {"id": up2["id"]}, "name": name}]}}})


def main():
    args = sys.argv[1:]
    if args[:1] == ["--preview"]:
        open("preview.png", "wb").write(render(args[1], args[2] if len(args) > 2 else ""))
        print("Wrote preview.png")
        return
    force = "--force" in args
    nt = Notion(os.environ["NOTION_TOKEN"])
    done = skipped = 0
    for i, page in enumerate(nt.pages(os.environ["NOTION_DATABASE_ID"])):
        props = page["properties"]
        if i == 0:
            print("Properties found:", ", ".join(f"{k} ({v['type']})" for k, v in props.items()))
            if HANZI_PROP not in props:
                sys.exit(f"No property named '{HANZI_PROP}'. Change HANZI_PROP at the top of the script.")
        hanzi = plain(props.get(HANZI_PROP))
        cover_col = props.get(COVER_PROP, {})
        has_cover = page.get("cover") and (cover_col.get("type") != "files" or cover_col["files"])
        if not hanzi or (has_cover and not force):
            print(f"- skipped {hanzi or '(empty Hanzi)'}: " + ("no Hanzi" if not hanzi else "already has a cover"))
            skipped += 1
            continue
        pinyin = plain(props.get(PINYIN_PROP)) if SHOW_PINYIN else ""
        nt.set_cover(page, render(hanzi, pinyin), f"{hanzi}.png")
        done += 1
        print(f"✓ {hanzi}")
    print(f"Done: {done} covers set, {skipped} skipped.")


if __name__ == "__main__":
    main()
