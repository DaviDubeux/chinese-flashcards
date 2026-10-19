#!/usr/bin/env python3
"""Escolhe flashcards aleatórios para revisar e marca esses cards.

Por padrão marca Revisar em 10 cards aleatórios: 5 Difícil, 3 Médio e 2 Fácil (pelo Status).
Se faltar card num status, o próximo status mais difícil completa, depois o próximo mais fácil.
Cards que já têm o valor, ou que têm outro status, nunca são escolhidos.

É o que o webhook do botão de revisão roda, e você pode rodar por conta própria:
  python3 pick_random.py --reset            # desmarca o grupo anterior e marca um novo
  python3 pick_random.py                    # marca mais 10, mantendo o grupo anterior

Opções:
  --prop NOME     a propriedade a marcar (padrão Revisar)
  --value VALOR   o valor a definir (padrão: marcado numa caixa de seleção, hoje numa data)
  --by NOME       a propriedade de dificuldade (padrão Status, senão a propriedade de
                  seleção ou status que tem os nomes do --mix)
  --mix MIX       quantos de cada, do mais difícil ao mais fácil (padrão Difícil:5,Médio:3,Fácil:2)
  --n N           só N cards aleatórios, ignorando a dificuldade
  --reset         primeiro limpa a propriedade em todos os cards (status não pode ser limpo)
  --db ID         o banco de dados (padrão NOTION_DATABASE_ID, senão o banco compartilhado
                  com a sua integração que tem a --prop)

Variáveis de ambiente:
  NOTION_TOKEN        o segredo da sua integração (ntn_...)
  NOTION_DATABASE_ID  opcional, veja --db
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
        raise PickError(f"nenhum banco compartilhado com a integração tem uma propriedade chamada '{name}'")
    return db


def pick_random(nt, db=None, name=PROP, mix=None, by=BY, value=None, reset=False):
    """Mark random cards. mix is [(status, count), ...] hardest first; with by="" it is
    [("", n)] and difficulty is ignored. Returns a summary line."""
    mix = mix or parse_mix(MIX)
    pages = list(nt.pages(db or find_database(nt, name)))
    if not pages or name not in pages[0]["properties"]:
        raise PickError(f"nenhuma propriedade chamada '{name}'")
    if by and by not in pages[0]["properties"]:  # find the property holding Difícil/Médio/Fácil
        names = {g.casefold() for g, _ in mix}
        by = next((k for k, v in pages[0]["properties"].items() if v["type"] in ("select", "status")
                   and any(current(p["properties"][k]).casefold() in names for p in pages)), None)
        if not by:
            raise PickError("nenhuma propriedade de seleção ou status com " + ", ".join(g for g, _ in mix))
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
    return f"✓ revisão: {name}={value} em {len(chosen)} cards ({cleared} desmarcados): " + ", ".join(words)


def main():
    ap = argparse.ArgumentParser(description="Escolhe flashcards aleatórios para revisar e marca esses cards.",
                                 add_help=False)
    ap.add_argument("-h", "--help", action="help", help="mostra esta ajuda")
    ap.add_argument("--prop", default=PROP, metavar="NOME", help=f"a propriedade a marcar (padrão {PROP})")
    ap.add_argument("--value", metavar="VALOR", help="o valor a definir (padrão: marcado, ou hoje numa data)")
    ap.add_argument("--by", default=BY, metavar="NOME", help=f"a propriedade de dificuldade (padrão {BY})")
    ap.add_argument("--mix", default=MIX, help=f"quantos de cada, do mais difícil ao mais fácil (padrão {MIX})")
    ap.add_argument("--n", type=int, help="só N cards aleatórios, ignorando a dificuldade")
    ap.add_argument("--reset", action="store_true", help="primeiro limpa a propriedade em todos os cards")
    ap.add_argument("--db", default=os.environ.get("NOTION_DATABASE_ID"), metavar="ID",
                    help="o id do banco de dados (padrão NOTION_DATABASE_ID)")
    a = ap.parse_args()
    token = os.environ.get("NOTION_TOKEN") or sys.exit("Defina NOTION_TOKEN primeiro (veja o README).")
    try:
        mix = [("", a.n)] if a.n else parse_mix(a.mix)
    except (ValueError, IndexError):
        sys.exit(f"O --mix deve ser no formato {MIX}")
    try:
        print(pick_random(Notion(token), a.db, a.prop, mix, "" if a.n else a.by, a.value, a.reset))
    except PickError as e:
        sys.exit(f"✗ {e}")


if __name__ == "__main__":
    main()
