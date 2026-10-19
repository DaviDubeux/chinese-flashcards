# Hanzi flashcards for Notion

Two small Python scripts for a Notion flashcard database:

- **`fill_card.py`** takes the word in a card's **Hanzi** field and fills the rest: a **cover** image of the characters, **Pinyin** (for example `wǒ`) and the **HSK** level (for example `HSK-1`).
- **`pick_random.py`** marks 10 random cards to review: 5 **Difícil**, 3 **Médio** and 2 **Fácil**.

You can run both yourself from your computer, with no server and no webhooks. If you want them to run on their own from Notion, see [Automate it with Notion webhooks](#automate-it-with-notion-webhooks) after that.

![Example cover](example_cover.png)

## Run the scripts yourself

### One-time setup
1. **Create a Notion integration.** Go to https://www.notion.so/profile/integrations, create an internal integration and copy its secret (it starts with `ntn_`).
2. **Give it your database.** Open the flashcards database in Notion, click **•••** › **Connections**, and add your integration.
3. **Copy the database id.** It's the 32 characters in the database link, before `?v=`: `notion.so/`**`1a2b3c...`**`?v=...`
4. **Install Python 3 and the requirements**, from this folder:
   ```
   pip install -r requirements.txt
   ```
5. **Set your secret and database id** in the terminal you'll run the scripts from:
   ```
   export NOTION_TOKEN=ntn_...
   export NOTION_DATABASE_ID=1a2b3c...
   ```
   On Windows PowerShell, use `$env:NOTION_TOKEN="ntn_..."` instead.

Your database needs a **Hanzi** title or text field. **Pinyin** (text) and **HSK** (select, text or number) are filled if they exist. To use other column names, change the settings at the top of `hanzi_covers.py`.

### Fill cards: `fill_card.py`
```
python3 fill_card.py --all            # every card: fill Pinyin and HSK, add missing covers
python3 fill_card.py --all --force    # the same, and redraw every cover
```
The first run downloads the font (26 MB) and the HSK word list once.

To fill only some cards, pass their links instead of `--all`. This always redraws their covers.
1. In Notion, open the card, click **•••** at the top right, and choose **Copy link**.
2. Paste the link after the script name, **inside quotes**:
   ```
   python3 fill_card.py "https://www.notion.so/me/学习-1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d?pvs=4"
   ```
   The quotes matter: without them, the `?` in the link makes the macOS terminal answer `no matches found`.
3. For several cards, add more links separated by spaces. The 32-character id at the end of the link also works on its own.

### Pick cards to review: `pick_random.py`
```
python3 pick_random.py --reset    # uncheck the last set, then check 10 new cards
python3 pick_random.py            # check 10 more, keeping the ones already checked
```
It sets the **Revisar** checkbox on 5 **Difícil**, 3 **Médio** and 2 **Fácil** cards, by the **Status** property. Cards that are already checked, or have any other status, are never picked.

If a status doesn't have enough cards, the next harder status completes it, then the next easier one. For example, with only 4 Difícil cards you get 4 Difícil + 4 Médio + 2 Fácil.

| Option | Default | What it does |
|---|---|---|
| `--prop` | `Revisar` | The property to set. Works with checkbox, select, status, multi-select, text, number and date properties. |
| `--value` | checked / today | What to set it to. |
| `--by` | `Status` | The difficulty property (status or select). |
| `--mix` | `Difícil:5,Médio:3,Fácil:2` | How many cards of each, hardest first. |
| `--n` | | `--n 10` picks 10 random cards and ignores difficulty. |
| `--reset` | | First clear the property on every card. Status properties can't be cleared. |
| `--db` | `NOTION_DATABASE_ID` | The database id. |

### Preview a cover
```
python3 hanzi_covers.py --preview 你好
```
This writes `preview.png` without touching Notion.

## Automate it with Notion webhooks
Notion can call the same scripts for you: an automation fills each new card, and a button picks the review set. For that, `server.py` has to run somewhere Notion can reach. These steps use [Render](https://render.com)'s free plan.

### 1. Host the server
1. Push this folder to a GitHub repository.
2. On Render, create a **Web Service** from that repository, with start command `python3 server.py`. It redeploys on every push.
3. Under **Environment**, add:
   - `NOTION_TOKEN`: your integration secret
   - `WEBHOOK_KEY`: any long random word you choose. It keeps strangers from using your server.
   - `NOTION_DATABASE_ID`: optional, the flashcards database id

The webhook URLs below use `https://YOUR-APP.onrender.com`; replace it with your Render address and `YOUR_WEBHOOK_KEY` with your key.

### 2. Fill new cards automatically
In the flashcards database, click **⚡** (Automations) › **New automation**:
- **Trigger:** *Page added*, and also *Hanzi edited* so Pinyin, HSK and the cover follow changes.
- **Action:** *Send webhook* to `https://YOUR-APP.onrender.com/?key=YOUR_WEBHOOK_KEY`

This runs `fill_card.py` on the card. A manual fix to Pinyin stays until you edit that card's Hanzi again.

### 3. Review button
Add a **Button** anywhere in Notion, inside the database or on another page, with the action *Send webhook* to:
```
https://YOUR-APP.onrender.com/random?key=YOUR_WEBHOOK_KEY&reset=1
```
This runs `pick_random.py --reset`. The URL takes the same options without the dashes, for example `&n=10` or `&mix=Difícil:6,Médio:4`. If the button isn't inside the database, the server uses `NOTION_DATABASE_ID`, or else finds the database shared with your integration that has a **Revisar** property.

If a webhook does nothing, check **Logs** on Render. A filled card shows `✓ 我 wǒ | HSK-1`, and a review pick shows `✓ random: Revisar=true on 10 cards ...`.

## Settings (top of `hanzi_covers.py`)
| Setting | Default | What it does |
|---|---|---|
| `HANZI_PROP`, `PINYIN_PROP`, `HSK_PROP` | `Hanzi`, `Pinyin`, `HSK` | Your column names. |
| `HSK_VERSION` | `"n"` (HSK 3.0, levels 1–7) | Use `"o"` for HSK 2.0 (levels 1–6). |
| `FILL_ONLY_EMPTY` | `False` | Set to `True` to never overwrite Pinyin or HSK once filled. |
| `SHOW_PINYIN` | `False` | Print pinyin on the cover. |

## Where the data comes from
- **Pinyin:** [pypinyin](https://github.com/mozillazg/python-pinyin) (MIT licence), which reads whole words so each character gets the right tone in context (晚上好 → wǎn shàng hǎo).
- **HSK level:** the [Complete HSK Vocabulary](https://github.com/drkameleon/complete-hsk-vocabulary) list (MIT licence, about 11,000 words), downloaded once as `hsk.json`. Words not in the list get no HSK level.
- **Cover font:** [LXGW WenKai GB](https://github.com/lxgw/LxgwWenKaiGB) (SIL Open Font License), so the covers are free to share.

## Known limits
- **Pinyin is lowercase with one syllable per character,** for example *zhōng guó*. Proper nouns aren't capitalised.
- **The first webhook after a pause can be slow.** Render's free plan sleeps after about 15 minutes without use and takes up to a minute to wake.
