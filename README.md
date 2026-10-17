# Hanzi cover button for Notion

Click a button on a flashcard, and a few seconds later the card gets a cover image of its hanzi.

Notion buttons can't run a script on your computer. They can only send a webhook (a request to a web address). So `server.py` runs online on Render's free plan and does the work when Notion calls it.

## Files

| File | What it is |
|---|---|
| `hanzi_covers.py` | Draws the image and talks to Notion. You can still run it on your computer for every card at once. |
| `server.py` | The small web service the button calls. |
| `requirements.txt` | The Python libraries Render installs. |

Anyone can use the same service: each person connects their own Notion on its home page, and no keys are shared.

## 1. Put the files on GitHub

1. Create a new **private** repository on github.com, for example `hanzi-covers`.
2. Click **Add file › Upload files** and upload `hanzi_covers.py`, `server.py`, `requirements.txt` and `.gitignore`. Don't upload the font or any token.

## 2. Run it on Render (free)

1. Sign up at render.com with your GitHub account.
2. Click **New › Web Service** and pick your repository.
3. Fill in the settings:
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `python server.py`
   - **Instance type:** Free
4. Under **Environment Variables**, add `SECRET_KEY`. Make up a long random value. Don't change it later, because changing it breaks everyone's buttons.
5. Click **Deploy** and note your address, for example `https://hanzi-covers.onrender.com`.

## 3. Make a public Notion integration

A *public* integration lets your friends click **Connect** and approve access themselves, so nobody has to copy or send a key.

1. Go to notion.so/profile/integrations and click **New integration**. Set **Type** to **Public**.
2. Fill in the form. For the website, privacy policy and terms links, you can use your Render address.
3. Under **Redirect URIs**, add your Render address followed by `/callback`, for example `https://hanzi-covers.onrender.com/callback`.
4. Under **Capabilities**, tick Read content, Update content and Insert content.
5. Optional: under **Notion URL for optional template**, paste the public link of an **empty** template (a copy of your database with the cards deleted). Friends who connect are then offered a copy of it, already connected. Leave this blank to share nothing.
6. Save, then copy the **OAuth client ID** and **OAuth client secret**.
7. Back on Render, add both as environment variables, `NOTION_CLIENT_ID` and `NOTION_CLIENT_SECRET`. Render redeploys on its own.

## 4. What you and each friend do

1. Open the Render address and click **Connect your Notion**.
2. Choose your flashcard database (or accept the template copy) and click **Allow access**.
3. Copy the personal button URL that the page shows you.
4. In the flashcard database, add a **Button** property called `Make cover`, set its action to **Send webhook**, and paste that URL.

Each person's button only reaches the pages they shared. Their access token sits inside their own button URL, encrypted, and is never stored on the server. A person can revoke access anytime in Notion under **Settings › Connections**.

## Good to know

- **The first click can be slow.** Render's free plan puts the service to sleep after about 15 minutes without use, and waking it takes up to a minute. If nothing happens, wait a moment and click again.
- **If nothing happens at all,** open your service on Render and click **Logs**. Each click shows `✓ 学` when it worked, or an error message.
- **Settings to change** are at the top of `hanzi_covers.py`: `HANZI_PROP`, `COVER_PROP`, `SHOW_PINYIN` and the colours. They apply to everyone. Commit the change on GitHub and Render redeploys.
- **Plan:** each person's workspace needs Notion Plus, Education Plus or higher, because Send webhook buttons aren't on the free plan.
- **Your old setup still works.** If you keep `NOTION_TOKEN` and `WEBHOOK_KEY` in Render, the `?key=WEBHOOK_KEY` button you already made keeps working.
