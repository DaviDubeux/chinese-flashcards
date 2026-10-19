#!/usr/bin/env python3
"""Pick random flashcards to review and mark them.

By default it sets Revisar on 10 random cards: 5 Difícil, 3 Médio and 2 Fácil (from Status).
A status short of cards is completed by the next harder status, then the next easier one.
Cards that already have the value, or have another status, are never picked.

This is what the review button's webhook runs, and you can run it yourself:
  python3 pick_random.py --reset            # clear the last set, then mark a new one
  python3 pick_random.py                    # mark 10 more, keeping the last set

Options:
  --prop NAME     the property to set (default Revisar)
  --value VALUE   what to set (default: checked for a checkbox, today for a date)
  --by NAME       the difficulty property (default Status, else the select/status
                  property that holds the --mix names)
  --mix MIX       how many of each, hardest first (default Difícil:5,Médio:3,Fácil:2)
  --n N           just N random cards, ignoring difficulty
  --reset         first clear the property on every card (status properties can't be cleared)
  --db ID         the database (default NOTION_DATABASE_ID, else the database shared with
                  your integration that has --prop)

Environment variables:
  NOTION_TOKEN        your integration secret (ntn_...)
  NOTION_DATABASE_ID  optional, see --db
"""
import argparse, datetime, os, random, sys

from hanzi_covers import HANZI_PROP, Notion, plain, prop_value

PROP, BY, MIX = "Revisar", "Status", "Difícil:5,Médio:3,Fácil:2"


class PickError(Exception):
    pass


def parse_mix(text):
    """"Difícil:5,Médio:3" -> [("Difícil", 5), ("Médio", 3)]. Raises ValueError."""
    return [(g.rsplit(":", 1)[0].strip(), int(g.rsplit(":", 1)[1])) for g in text.split(",")]


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


def pick(groups, quotas):
    """Pick quotas[i] random cards from groups[i] (hardest first). A group short of cards is
    completed from the nearest harder group, then the nearest easier one."""
    left = [random.sample(g, len(g)) for g in groups]
    chosen = [[left[i].pop() for _ in range(min(q, len(left[i])))] for i, q in enumerate(quotas)]
    for i, q in enumerate(quotas):
        for j in list(range(i - 1, -1, -1)) + list(range(i + 1, len(groups))):
            while len(chosen[i]) < q and left[j]:
                chosen[i].append(left[j].pop())
    return [p for c in chosen for p in c]


def find_database(nt, name):
    """The database shared with the integration that has a property called name."""
    dbs = nt.call("POST", "/search", json={"filter": {"property": "object", "value": "database"}})
    db = next((d["id"] for d in dbs["results"] if name in d.get("properties", {})), None)
    if not db:
        raise PickError(f"no database with a property named '{name}' is shared with the integration")
    return db


def pick_random(nt, db=None, name=PROP, mix=None, by=BY, value=None, reset=False):
    """Mark random cards. mix is [(status, count), ...] hardest first; with by="" it is
    [("", n)] and difficulty is ignored. Returns a summary line."""
    mix = mix or parse_mix(MIX)
    pages = list(nt.pages(db or find_database(nt, name)))
    if not pages or name not in pages[0]["properties"]:
        raise PickError(f"no property named '{name}'")
    if by and by not in pages[0]["properties"]:  # find the property holding Difícil/Médio/Fácil
        names = {g.casefold() for g, _ in mix}
        by = next((k for k, v in pages[0]["properties"].items() if v["type"] in ("select", "status")
                   and any(current(p["properties"][k]).casefold() in names for p in pages)), None)
        if not by:
            raise PickError("no select or status property holding " + ", ".join(g for g, _ in mix))
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
    if by:
        level = lambda p: current(p["properties"][by]).strip().casefold()
        groups = [[p for p in pool if level(p) == g.casefold()] for g, _ in mix]
    else:
        groups = [pool]
    chosen = pick(groups, [q for _, q in mix])
    for p in chosen:
        nt.call("PATCH", f"/pages/{p['id']}", json={"properties": {name: target}})
    words = [(plain(p["properties"].get(HANZI_PROP)) or p["id"]) + (f" ({current(p['properties'][by])})" if by else "")
             for p in chosen]
    return f"✓ random: {name}={value} on {len(chosen)} cards ({cleared} cleared): " + ", ".join(words)


def main():
    ap = argparse.ArgumentParser(description="Pick random flashcards to review and mark them.",
                                 epilog="Run with -h for the defaults; the top of this file explains each option.")
    ap.add_argument("--prop", default=PROP)
    ap.add_argument("--value")
    ap.add_argument("--by", default=BY)
    ap.add_argument("--mix", default=MIX)
    ap.add_argument("--n", type=int)
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--db", default=os.environ.get("NOTION_DATABASE_ID"))
    a = ap.parse_args()
    token = os.environ.get("NOTION_TOKEN") or sys.exit("Set NOTION_TOKEN first (see the README).")
    try:
        mix = [("", a.n)] if a.n else parse_mix(a.mix)
    except (ValueError, IndexError):
        sys.exit(f"--mix should look like {MIX}")
    try:
        print(pick_random(Notion(token), a.db, a.prop, mix, "" if a.n else a.by, a.value, a.reset))
    except PickError as e:
        sys.exit(f"✗ {e}")


if __name__ == "__main__":
    main()
