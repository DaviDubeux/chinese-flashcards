#!/usr/bin/env python3
"""Código compartilhado: desenha as capas com os Hanzi e conversa com o Notion.

O Pinyin vem do pypinyin, o nível HSK da lista de palavras do HSK (baixada uma vez).
Você não roda este arquivo para atualizar cards; use fill_card.py e pick_random.py.
Para ver como uma capa fica, sem nenhuma chamada ao Notion:
  python3 hanzi_covers.py --preview 你好   # gera preview.png

Os nomes das propriedades ficam logo abaixo (HANZI_PROP, PINYIN_PROP). O Pinyin é opcional.
A fonte é a LXGW WenKai GB, uma Kai no estilo de livro didático (SIL Open Font License),
então as imagens podem ser compartilhadas livremente.
"""
import io, json, os, re, sys, time
import requests
from pypinyin import Style, pinyin as to_pinyin
from PIL import Image, ImageDraw, ImageFont

HANZI_PROP = "Hanzi"     # propriedade de título ou texto com o(s) caractere(s)
PINYIN_PROP = "Pinyin"   # propriedade de texto opcional; ignorada se não existir
SHOW_PINYIN = False      # True mostra o pinyin embaixo dos caracteres
COVER_PROP = "Cover"     # propriedade opcional de Arquivos e mídia; também recebe a imagem se existir
HSK_PROP = "HSK"         # propriedade de seleção (ou texto/número), preenchida como "HSK-1"
HSK_VERSION = "n"        # "o" = HSK 2.0 (níveis 1-6), "n" = HSK 3.0 (níveis 1-7)
FILL_ONLY_EMPTY = False  # False: Pinyin/HSK acompanham o Hanzi toda vez que a automação roda
WIDTH, HEIGHT = 1500, 600  # Notion's cover size (shown center-cropped)
BG, FG, SUB = "#FBF7EF", "#B22222", "#555555"

FONT_URL = "https://raw.githubusercontent.com/lxgw/LxgwWenKaiGB/main/fonts/TTF/LXGWWenKaiGB-Medium.ttf"
FONT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "LXGWWenKaiGB-Medium.ttf")
API = "https://api.notion.com/v1"
# HSK word list (MIT licence): github.com/drkameleon/complete-hsk-vocabulary
HSK_URL = "https://raw.githubusercontent.com/drkameleon/complete-hsk-vocabulary/main/complete.min.json"
HSK_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hsk.json")
_hsk = None


def font(size):
    if not os.path.exists(FONT_PATH):
        print("Baixando a fonte LXGW WenKai GB...")
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
            print("Baixando a lista de palavras do HSK...")
            r = requests.get(HSK_URL, timeout=120)
            r.raise_for_status()
            with open(HSK_PATH, "wb") as fh:
                fh.write(r.content)
        with open(HSK_PATH, encoding="utf-8") as fh:
            _hsk = {e["s"]: e for e in json.load(fh)}
    return _hsk


def word_pinyin(hanzi):
    """Pinyin with tone marks, one syllable per character, e.g. 晚上好 -> "wǎn shàng hǎo".
    pypinyin knows whole words, so characters with several readings come out right in context."""
    return " ".join(s[0] for s in to_pinyin(hanzi, style=Style.TONE))


def lookup(hanzi):
    """Pinyin and HSK level ("HSK-1", or "" if the word isn't in the HSK list)."""
    entry = hsk_words().get(hanzi)
    levels = sorted(int(l[1:]) for l in entry["l"] if l[0] == HSK_VERSION) if entry else []
    return {"pinyin": word_pinyin(hanzi), "hsk": f"HSK-{levels[0]}" if levels else ""}


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

    def fill_fields(self, page, only_empty=None):
        """Fill Pinyin and HSK level. Returns what was written.
        only_empty: True keeps fields that are already filled (default FILL_ONLY_EMPTY)."""
        only_empty = FILL_ONLY_EMPTY if only_empty is None else only_empty
        props = page["properties"]
        hanzi = plain(props.get(HANZI_PROP))
        targets = {"pinyin": PINYIN_PROP, "hsk": HSK_PROP}
        todo = {k: n for k, n in targets.items()
                if n in props and (not only_empty or is_empty(props[n]))}
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
    if args[:1] != ["--preview"] or len(args) < 2:
        sys.exit("Uso: python3 hanzi_covers.py --preview 你好 [pinyin]\n"
                 "Para atualizar cards, use fill_card.py ou pick_random.py.")
    open("preview.png", "wb").write(render(args[1], args[2] if len(args) > 2 else ""))
    print("preview.png gerado")


if __name__ == "__main__":
    main()
