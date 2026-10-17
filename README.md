# Hanzi cover button for Notion

Click a button on a flashcard, and a few seconds later the card gets a cover image of its hanzi.

Notion buttons can't run a script on your computer. They can only send a webhook (a request to a web address). So `server.py` runs online on Render's free plan and does the work when Notion calls it.

## Files

| File | What it is |
|---|---|
| `hanzi_covers.py` | Draws the image and talks to Notion. You can still run it on your computer for every card at once. |
| `server.py` | The small web service the button calls. |
| `requirements.txt` | The Python libraries Render installs. |

## 1. Put the files on GitHub

1. Create a new **private** repository on github.com, for example `hanzi-covers`.
2. Click **Add file › Upload files** and upload `hanzi_covers.py`, `server.py`, `requirements.txt` and `.gitignore`. Don't upload the font or any token.

## 2. Run it on Render (free)

1. Sign up at render.com with your GitHub account.
2. Click **New › Web Service** and pick your `hanzi-covers` repository.
3. Fill in the settings:
   - **Runtime:** Python
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `python server.py`
   - **Instance type:** Free
4. Under **Environment Variables**, add these:
   - `NOTION_TOKEN`: your Hanzi Cover integration secret (`ntn_...`)
   - `WEBHOOK_KEY`: a long random word you make up, for example `xue-7f3k9q2m`. It stops strangers from triggering your service.
5. Click **Deploy**. When it finishes, Render shows your service's address, for example `https://hanzi-covers.onrender.com`. Open it in a browser. It should say *Hanzi cover service is running.*

## 3. Add the button in Notion

1. In your flashcard database, add a new property of type **Button** and name it something like `Make cover`.
2. Set the action to **Send webhook**.
3. For the URL, use your Render address followed by `/?key=` and your WEBHOOK_KEY:
   `https://hanzi-covers.onrender.com/?key=xue-7f3k9q2m`
4. Under properties to send, include **Hanzi**.
5. Click **Save**. Every card now has a **Make cover** button.

## Good to know

- **The first click can be slow.** Render's free plan puts the service to sleep after about 15 minutes without use, and waking it takes up to a minute. If nothing happens, wait a moment and click again. You can also open the Render address in your browser first to wake it.
- **If nothing happens at all,** open your service on Render and click **Logs**. Each click shows `✓ 学` when it worked, or an error message.
- **Settings to change** are at the top of `hanzi_covers.py`: `HANZI_PROP`, `COVER_PROP`, `SHOW_PINYIN` and the colours. Commit the change on GitHub and Render redeploys on its own.
- **Your classmates can use the button too.** The covers are made with your integration, so anyone who can edit the database can click it.
