#!/usr/bin/env python3
"""Preenche os flashcards a partir do campo Hanzi: capa, Pinyin e nível HSK.

É o que o webhook de card novo roda, e você pode rodar por conta própria:
  python3 fill_card.py "<link do card>" [...]   # preenche esses cards e redesenha as capas
  python3 fill_card.py --all                    # todos os cards: preenche campos vazios, cria capas que faltam
  python3 fill_card.py --all --force            # todos os cards, refazendo Pinyin, HSK e todas as capas

Coloque o link entre aspas (no Notion: ••• › Copiar link). O id de 32 caracteres também funciona.

Variáveis de ambiente:
  NOTION_TOKEN        o segredo da sua integração (ntn_...)
  NOTION_DATABASE_ID  o banco de flashcards, só necessário com --all
"""
import os, re, sys

from hanzi_covers import COVER_PROP, HANZI_PROP, Notion, plain


def page_id(link):
    """The page id from a Notion link like notion.so/Card-1a2b...?v=..., or the id itself."""
    ids = re.findall(r"[0-9a-f]{32}|[0-9a-f-]{36}", link.split("?")[0].lower())
    if not ids:
        sys.exit(f"Isso não é um link nem um id de página do Notion: {link}")
    return ids[-1]


def fill_card(nt, page, cover=True, only_empty=None):
    """Fill Pinyin and HSK, and draw the cover if cover is True.
    Returns (hanzi, what was filled), or (None, {}) when the Hanzi field is empty."""
    hanzi = plain(page["properties"].get(HANZI_PROP))
    if not hanzi:
        return None, {}
    filled = nt.fill_fields(page, only_empty)
    if cover:
        nt.cover_page(page)
    return hanzi, filled


def log_line(page, hanzi, filled):
    return f"✓ {hanzi} " + " | ".join(filled.values()) if hanzi else f"- {page['id']}: campo Hanzi vazio"


def fill_all(nt, db, force=False):
    done = skipped = 0
    for i, page in enumerate(nt.pages(db)):
        props = page["properties"]
        if i == 0:
            print("Propriedades encontradas:", ", ".join(f"{k} ({v['type']})" for k, v in props.items()))
            if HANZI_PROP not in props:
                sys.exit(f"Nenhuma propriedade chamada '{HANZI_PROP}'. Mude HANZI_PROP no topo de hanzi_covers.py.")
        cover_col = props.get(COVER_PROP, {})
        has_cover = page.get("cover") and (cover_col.get("type") != "files" or cover_col["files"])
        # Without --force, keep Pinyin and HSK you already filled (or fixed by hand).
        hanzi, filled = fill_card(nt, page, cover=force or not has_cover, only_empty=not force)
        if hanzi and (filled or not has_cover or force):
            done += 1
            print(log_line(page, hanzi, filled))
        else:
            skipped += 1
    print(f"Pronto: {done} cards atualizados, {skipped} já estavam completos.")


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        sys.exit(__doc__)
    token = os.environ.get("NOTION_TOKEN") or sys.exit("Defina NOTION_TOKEN primeiro (veja o README).")
    nt = Notion(token)
    if "--all" in args:
        db = os.environ.get("NOTION_DATABASE_ID") or sys.exit("Defina NOTION_DATABASE_ID para usar --all.")
        fill_all(nt, db, force="--force" in args)
        return
    for link in args:
        page = nt.page(page_id(link))
        print(log_line(page, *fill_card(nt, page)))


if __name__ == "__main__":
    main()
