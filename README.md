# Hanzi flashcard button for Notion

Type a word in **Hanzi**, click **Make cover**, and a few seconds later the card has:
- a **cover** image of the characters
- **Pinyin**, for example `wǒ`
- **Tradução**, for example `Eu`
- **HSK**, for example `HSK-1`

Fields you've already filled are left alone, so your own corrections stick. The cover is always redrawn.

## Where the data comes from
- **Pinyin:** [pypinyin](https://github.com/mozillazg/python-pinyin) (MIT licence), which reads whole words so each character gets the right tone in context (晚上好 → wǎn shàng hǎo).
- **HSK level and meaning:** the [Complete HSK Vocabulary](https://github.com/drkameleon/complete-hsk-vocabulary) list (MIT licence, about 11,000 words). It's downloaded once as `hsk.json`.
- **Tradução:** the free [MyMemory](https://mymemory.translated.net) translation API. It needs no key and allows about 5,000 characters a day, which is plenty for flashcards. It translates the word's main English meaning into Portuguese.
- **Words not in the HSK list:** Tradução is translated straight from Chinese, and HSK stays empty.

## Setup
1. Push `hanzi_covers.py`, `server.py`, `requirements.txt` and `.gitignore` to your GitHub repository. Render redeploys on its own.
2. On Render, keep `NOTION_TOKEN` (your Hanzi Cover secret) and `WEBHOOK_KEY`.
3. Your Notion button stays the same: **Send webhook** to `https://chinese-flashcards-pjkb.onrender.com/?key=YOUR_WEBHOOK_KEY`.

## Fill all your cards at once (on your computer)
```
NOTION_TOKEN=ntn_... NOTION_DATABASE_ID=... python3 hanzi_covers.py
```
This fills empty Pinyin, Tradução and HSK fields on every card and adds any missing covers. Add `--force` to redraw every cover.

## Settings (top of `hanzi_covers.py`)
| Setting | Default | What it does |
|---|---|---|
| `HSK_VERSION` | `"o"` (HSK 2.0, levels 1–6) | Use `"n"` for HSK 3.0 (levels 1–7). |
| `FILL_ONLY_EMPTY` | `True` | Set to `False` to overwrite fields on every click. |
| `SHOW_PINYIN` | `False` | Print pinyin on the cover. |
| `TRANSLATE_TO` | `"pt-BR"` | Translation language. |
| `PINYIN_PROP`, `TRANSLATION_PROP`, `HSK_PROP` | `Pinyin`, `Tradução`, `HSK` | Your column names. |

## Known limits
- **Pinyin is lowercase with one syllable per character,** for example *zhōng guó*. Proper nouns aren't capitalised.
- **Machine translations** are short and sometimes odd. Check them like any dictionary.
- **The first click can be slow.** Render's free plan sleeps after about 15 minutes without use and takes up to a minute to wake.
- **If nothing happens,** check **Logs** on Render. A successful click shows `✓ 我 wǒ | Eu | HSK-1`.
