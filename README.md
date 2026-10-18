# Hanzi flashcard automation for Notion

Type a word in **Hanzi**, and a few seconds later the card has:
- a **cover** image of the characters
- **Pinyin**, for example `wǒ`
- **HSK**, for example `HSK-1`

The Notion automation runs this whenever a card is created or its Hanzi is edited, so Pinyin, HSK and the cover always match the current Hanzi. A manual fix to Pinyin stays until you edit that card's Hanzi again.

## Where the data comes from
- **Pinyin:** [pypinyin](https://github.com/mozillazg/python-pinyin) (MIT licence), which reads whole words so each character gets the right tone in context (晚上好 → wǎn shàng hǎo).
- **HSK level:** the [Complete HSK Vocabulary](https://github.com/drkameleon/complete-hsk-vocabulary) list (MIT licence, about 11,000 words). It's downloaded once as `hsk.json`.
- **Words not in the HSK list:** HSK stays empty.

## Setup
1. Push `hanzi_covers.py`, `server.py`, `requirements.txt` and `.gitignore` to your GitHub repository. Render redeploys on its own.
2. On Render, keep `NOTION_TOKEN` (your Hanzi Cover secret) and `WEBHOOK_KEY`.
3. Your Notion database automation (trigger: page added, or Hanzi edited) uses **Send webhook** to `https://chinese-flashcards-pjkb.onrender.com/?key=YOUR_WEBHOOK_KEY`.

## Button: pick cards to review
A Notion button sets **Revisar** on 10 random cards: 5 **Difícil**, 3 **Médio** and 2 **Fácil** (from the **Status** property).
If a status doesn't have enough cards, the next harder status completes it, then the next easier one. For example, with only 4 Difícil cards you get 4 Difícil + 4 Médio + 2 Fácil. Cards with any other status are never picked.

1. Make sure your Hanzi Cover integration is connected to the database (it already is if covers work).
2. Add a button with the action **Send webhook** to
   `https://chinese-flashcards-pjkb.onrender.com/random?key=YOUR_WEBHOOK_KEY&reset=1`

Each click unchecks the previous set (`reset=1`) and checks a new one among cards that weren't checked. Leave out `reset=1` to keep adding cards instead.

| Option | Default | What it does |
|---|---|---|
| `prop` | `Revisar` | The property to set. Works with checkbox, select, status, multi-select, text, number and date properties. |
| `by` | `Status` | The difficulty property (status or select). |
| `mix` | `Difícil:5,Médio:3,Fácil:2` | How many cards of each, hardest first. |
| `n` | | `n=10` picks 10 random cards and ignores difficulty. |
| `value` | checked / today | What to set. |
| `reset` | | `1` first clears the property on every card. Status properties can't be cleared. |
| `db` | | The database id. Only needed if the button isn't on a page inside Flashcards; you can set `NOTION_DATABASE_ID` on Render instead. |

The Render log shows the picked cards, for example `✓ random: Revisar=true on 10 cards (10 cleared): 我 (Difícil), ...`.

## Fill all your cards at once (on your computer)
```
NOTION_TOKEN=ntn_... NOTION_DATABASE_ID=... python3 hanzi_covers.py
```
This fills empty Pinyin and HSK fields on every card and adds any missing covers. Add `--force` to redraw every cover.

## Settings (top of `hanzi_covers.py`)
| Setting | Default | What it does |
|---|---|---|
| `HSK_VERSION` | `"n"` (HSK 3.0, levels 1–7) | Use `"o"` for HSK 2.0 (levels 1–6). |
| `FILL_ONLY_EMPTY` | `False` | Set to `True` to never overwrite Pinyin or HSK once filled. |
| `SHOW_PINYIN` | `False` | Print pinyin on the cover. |
| `PINYIN_PROP`, `HSK_PROP` | `Pinyin`, `HSK` | Your column names. |

## Known limits
- **Pinyin is lowercase with one syllable per character,** for example *zhōng guó*. Proper nouns aren't capitalised.
- **The first update can be slow.** Render's free plan sleeps after about 15 minutes without use and takes up to a minute to wake.
- **If nothing happens,** check **Logs** on Render. A successful update shows `✓ 我 wǒ | HSK-1`.
