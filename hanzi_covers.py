#!/usr/bin/env python3
"""Fill each Notion flashcard from its Hanzi field: page cover, Pinyin, Tradução and HSK.

Pinyin comes from pypinyin, the HSK level from the HSK word list (downloaded once); the Portuguese
translation comes from the free MyMemory API. Fields you already filled are left alone.

Setup:
  1. Create an integration at https://www.notion.so/profile/integrations and copy its token.
  2. Open your flashcard database in Notion > ••• > Connections > add the integration.
  3. pip install -r requirements.txt
  4. export NOTION_TOKEN=secret_...   NOTION_DATABASE_ID=<32-char id from the database URL>
  5. python3 hanzi_covers.py            # fill empty fields, add missing covers
     python3 hanzi_covers.py --force    # also redo every cover
     python3 hanzi_covers.py --preview 你好   # just write preview.png, no Notion calls

Property names are set below (HANZI_PROP, PINYIN_PROP). Pinyin is optional.
The font is Noto Serif SC (SIL Open Font License), so the images are free to share.
"""
import io, json, os, re, sys, time
import requests
from pypinyin import Style, pinyin as to_pinyin
from PIL import Image, ImageDraw, ImageFont

HANZI_PROP = "Hanzi"     # title or text property holding the character(s)
PINYIN_PROP = "Pinyin"   # optional text property; ignored if missing
SHOW_PINYIN = False      # set to True to print pinyin under the characters
COVER_PROP = "Cover"     # optional Files & media property; also filled with the image if it exists
TRANSLATION_PROP = "Tradução"  # text property for the Portuguese translation
HSK_PROP = "HSK"         # select (or text/number) property, filled as e.g. "HSK-1"
HSK_VERSION = "o"        # "o" = HSK 2.0 (levels 1-6), "n" = HSK 3.0 (levels 1-7)
FILL_ONLY_EMPTY = True   # never overwrite Pinyin/Tradução/HSK you already typed
TRANSLATE_TO = "pt-BR"     # Portuguese (Brazil); Tradução stays empty if no translation is found
WIDTH, HEIGHT = 1500, 600  # Notion's cover size (shown center-cropped)
BG, FG, SUB = "#FBF7EF", "#B22222", "#555555"

FONT_URL = "https://raw.githubusercontent.com/notofonts/noto-cjk/main/Serif/SubsetOTF/SC/NotoSerifSC-Bold.otf"
FONT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "NotoSerifSC-Bold.otf")
API = "https://api.notion.com/v1"
# HSK word list with pinyin and English meanings (MIT licence): github.com/drkameleon/complete-hsk-vocabulary
HSK_URL = "https://raw.githubusercontent.com/drkameleon/complete-hsk-vocabulary/main/complete.min.json"
HSK_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hsk.json")
_hsk = None


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


def hsk_words():
    global _hsk
    if _hsk is None:
        if not os.path.exists(HSK_PATH):
            print("Downloading HSK word list...")
            r = requests.get(HSK_URL, timeout=120)
            r.raise_for_status()
            with open(HSK_PATH, "wb") as fh:
                fh.write(r.content)
        with open(HSK_PATH, encoding="utf-8") as fh:
            _hsk = {e["s"]: e for e in json.load(fh)}
    return _hsk


def main_form(entry):
    # Skip proper-noun readings (capitalised pinyin, e.g. 还 "Huán", a surname).
    forms = [f for f in entry["f"] if not f["i"]["y"][:1].isupper()] or entry["f"]
    return forms[0]


def translate(text, source):
    """Translate with free services that need no key: Google's public endpoint first (better
    quality for single words and names), then MyMemory. Returns "" if both fail; the reason is
    printed, so it shows in Render's logs."""
    try:
        r = requests.get("https://translate.googleapis.com/translate_a/single",
                         params={"client": "gtx", "sl": source, "tl": TRANSLATE_TO.split("-")[0],
                                 "dt": "t", "q": text}, timeout=20)
        r.raise_for_status()
        out = "".join(part[0] for part in r.json()[0] if part and part[0]).strip()
        if out and out.lower() != text.lower():
            return out
        print(f"Google gave no translation for {text!r}", flush=True)
    except Exception as e:
        print(f"Google translate failed for {text!r}: {e}", flush=True)
    try:
        r = requests.get("https://api.mymemory.translated.net/get",
                         params={"q": text, "langpair": f"{source}|{TRANSLATE_TO}"}, timeout=20)
        d = r.json()
        out = (d.get("responseData") or {}).get("translatedText", "").strip()
        if str(d.get("responseStatus")) == "200" and out and out.lower() != text.lower() \
                and not out.upper().startswith(("MYMEMORY WARNING", "QUERY LENGTH")):
            return out
        print(f"MyMemory gave no translation for {text!r}: {d.get('responseDetails') or out}", flush=True)
    except Exception as e:
        print(f"MyMemory failed for {text!r}: {e}", flush=True)
    return ""


def word_pinyin(hanzi):
    """Pinyin with tone marks, one syllable per character, e.g. 晚上好 -> "wǎn shàng hǎo".
    pypinyin knows whole words, so characters with several readings come out right in context."""
    return " ".join(s[0] for s in to_pinyin(hanzi, style=Style.TONE))


def lookup(hanzi):
    """Pinyin, Portuguese translation and HSK level ("HSK-1", or "" if not in the list)."""
    entry = hsk_words().get(hanzi)
    if entry:
        form = main_form(entry)
        english = re.sub(r"\(.*?\)", "", form["m"][0]).split(";")[0].strip()
        levels = sorted(int(l[1:]) for l in entry["l"] if l[0] == HSK_VERSION)
        return {"pinyin": word_pinyin(hanzi),
                "translation": translate(english, "en"),
                "hsk": f"HSK-{levels[0]}" if levels else ""}
    # Not an HSK word: translate the Chinese directly.
    return {"pinyin": word_pinyin(hanzi), "translation": translate(hanzi, "zh-CN"), "hsk": ""}


def prop_value(prop, value):
    """Notion property payload for a text, select or number property."""
    kind = prop["type"]
    if kind in ("rich_text", "title"):
        return {kind: [{"text": {"content": value}}]}
    if kind == "select":
        return {"select": {"name": value}}
    if kind == "multi_select":
        return {"multi_select": [{"name": value}]}
    if kind == "number":
        digits = re.sub(r"\D", "", value)
        return {"number": int(digits)} if digits else None
    return None


def is_empty(prop):
    kind = prop["type"]
    value = prop.get(kind)
    return value in (None, [], "") or (kind in ("rich_text", "title") and not plain(prop))


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

    def fill_fields(self, page):
        """Fill Pinyin, Tradução and HSK from the word lists. Returns what was written."""
        props = page["properties"]
        hanzi = plain(props.get(HANZI_PROP))
        targets = {"pinyin": PINYIN_PROP, "translation": TRANSLATION_PROP, "hsk": HSK_PROP}
        todo = {k: n for k, n in targets.items()
                if n in props and (not FILL_ONLY_EMPTY or is_empty(props[n]))}
        if not hanzi or not todo:
            return {}
        info = lookup(hanzi)
        update = {}
        for key, name in todo.items():
            value = prop_value(props[name], info[key]) if info[key] else None
            if value:
                update[name] = value
        if update:
            self.call("PATCH", f"/pages/{page['id']}", json={"properties": update})
        return {k: info[k] for k, n in todo.items() if n in update}

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
        if not hanzi:
            skipped += 1
            continue
        filled = nt.fill_fields(page)
        cover_col = props.get(COVER_PROP, {})
        has_cover = page.get("cover") and (cover_col.get("type") != "files" or cover_col["files"])
        if not has_cover or force:
            nt.cover_page(page)
        if filled or not has_cover or force:
            done += 1
            print(f"✓ {hanzi} " + " | ".join(filled.values()))
        else:
            skipped += 1
    print(f"Done: {done} cards updated, {skipped} already complete.")


if __name__ == "__main__":
    main()
