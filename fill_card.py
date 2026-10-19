#!/usr/bin/env python3
"""Fill flashcards from their Hanzi field: page cover, Pinyin and HSK level.

This is what the "new card" webhook runs, and you can run it yourself:
  python3 fill_card.py <card link or id> [...]   # fill these cards and redraw their covers
  python3 fill_card.py --all                     # every card: fill fields, add missing covers
  python3 fill_card.py --all --force             # every card, and redraw every cover

Environment variables:
  NOTION_TOKEN        your integration secret (ntn_...)
  NOTION_DATABASE_ID  the flashcards database, only needed for --all
"""
import os, re, sys

from hanzi_covers import COVER_PROP, HANZI_PROP, Notion, plain


def page_id(link):
    """The page id from a Notion link like notion.so/Card-1a2b...?v=..., or the id itself."""
    ids = re.findall(r"[0-9a-f]{32}|[0-9a-f-]{36}", link.split("?")[0].lower())
    if not ids:
        sys.exit(f"Not a Notion page link or id: {link}")
    return ids[-1]


def fill_card(nt, page, cover=True):
    """Fill Pinyin and HSK, and draw the cover if cover is True.
    Returns (hanzi, what was filled), or (None, {}) when the Hanzi field is empty."""
    hanzi = plain(page["properties"].get(HANZI_PROP))
    if not hanzi:
        return None, {}
    filled = nt.fill_fields(page)
    if cover:
        nt.cover_page(page)
    return hanzi, filled


def log_line(page, hanzi, filled):
    return f"✓ {hanzi} " + " | ".join(filled.values()) if hanzi else f"- {page['id']}: empty Hanzi field"


def fill_all(nt, db, force=False):
    done = skipped = 0
    for i, page in enumerate(nt.pages(db)):
        props = page["properties"]
        if i == 0:
            print("Properties found:", ", ".join(f"{k} ({v['type']})" for k, v in props.items()))
            if HANZI_PROP not in props:
                sys.exit(f"No property named '{HANZI_PROP}'. Change HANZI_PROP at the top of hanzi_covers.py.")
        cover_col = props.get(COVER_PROP, {})
        has_cover = page.get("cover") and (cover_col.get("type") != "files" or cover_col["files"])
        hanzi, filled = fill_card(nt, page, cover=force or not has_cover)
        if hanzi and (filled or not has_cover or force):
            done += 1
            print(log_line(page, hanzi, filled))
        else:
            skipped += 1
    print(f"Done: {done} cards updated, {skipped} already complete.")


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        sys.exit(__doc__)
    token = os.environ.get("NOTION_TOKEN") or sys.exit("Set NOTION_TOKEN first (see the README).")
    nt = Notion(token)
    if "--all" in args:
        db = os.environ.get("NOTION_DATABASE_ID") or sys.exit("Set NOTION_DATABASE_ID to use --all.")
        fill_all(nt, db, force="--force" in args)
        return
    for link in args:
        page = nt.page(page_id(link))
        print(log_line(page, *fill_card(nt, page)))


if __name__ == "__main__":
    main()
