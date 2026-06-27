# LinkedIn Job Email Bot 🤖

WhatsApp bot that reads LinkedIn job posts (text or screenshot), extracts the HR's email, and sends a personalised application email — all from a WhatsApp chat.

## How it works

```
You (WhatsApp) ──► Bot reads post ──► Claude extracts email + job info
                                              │
                              Claude drafts personalised email
                                              │
              You review the draft ──► Reply SEND ──► Gmail sends email to HR
```

---

## Prerequisites

- Python 3.9+
- A free [Twilio account](https://www.twilio.com/try-twilio)
- A [Gmail account](https://gmail.com) (used to send emails)
- An [Anthropic API key](https://console.anthropic.com)
- A [Railway account](https://railway.app) (free, for hosting)

---

## Setup (one-time, ~20 minutes)

### Step 1 — Edit your profile

Open `user_profile.json` and fill in **your** details:

```json
{
  "name": "Ravi Sharma",
  "current_role": "Data Engineer",
  "years_experience": 4,
  "skills": ["Python", "SQL", "Spark", "Airflow", "dbt", "AWS"],
  "brief_summary": "...",
  "linkedin": "https://linkedin.com/in/ravi-sharma",
  "portfolio": "https://github.com/ravisharma"
}
```

This is what Claude uses to write your application emails.

---

### Step 2 — Get a Gmail App Password

Your bot will send emails **from your Gmail account**.

1. Go to [myaccount.google.com/security](https://myaccount.google.com/security)
2. Enable **2-Step Verification** if not already on
3. Search for "App passwords" in the search bar
4. Create a new app password → select **Mail** + **Other (custom name)** → name it "Job Bot"
5. Copy the 16-character password shown (e.g. `abcd efgh ijkl mnop`)
6. This is your `GMAIL_APP_PASSWORD` (remove spaces when pasting)

---

### Step 3 — Set up Twilio WhatsApp Sandbox

1. Sign in to [console.twilio.com](https://console.twilio.com)
2. Go to **Messaging → Try it out → Send a WhatsApp message**
3. Follow the instructions to join the sandbox:
   - Save the number `+1 415 523 8886` in your contacts
   - Send the join code (e.g. `join sparkling-fox`) to that number on WhatsApp
4. Note your **Account SID** and **Auth Token** from the Twilio Console home page

> For production (your own WhatsApp number), you'll need to apply for a WhatsApp Business account via Twilio — but the sandbox is free and works perfectly for personal use.

---

### Step 4 — Get your Anthropic API key

1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Navigate to **API Keys** → **Create Key**
3. Copy the key (starts with `sk-ant-...`)

---

### Step 5 — Deploy to Railway

Railway gives you a free hosted server with a public URL.

1. Create a free account at [railway.app](https://railway.app)
2. Install the Railway CLI:
   ```bash
   npm install -g @railway/cli
   railway login
   ```
3. In the `linkedin_job_bot` folder:
   ```bash
   railway init          # creates a new project
   railway up            # deploys the app
   ```
4. Get your public URL:
   ```bash
   railway domain
   ```
   It will look like `https://linkedin-job-bot-production.up.railway.app`

5. Set environment variables on Railway:
   ```bash
   railway variables set ANTHROPIC_API_KEY=sk-ant-...
   railway variables set TWILIO_ACCOUNT_SID=AC...
   railway variables set TWILIO_AUTH_TOKEN=...
   railway variables set TWILIO_WHATSAPP_NUMBER="whatsapp:+14155238886"
   railway variables set GMAIL_ADDRESS=your.email@gmail.com
   railway variables set GMAIL_APP_PASSWORD=abcdefghijklmnop
   ```

> **Alternative:** You can also push to GitHub and connect the repo to Railway via the web dashboard — no CLI needed.

---

### Step 6 — Connect Twilio to your server

1. Back in Twilio Console → **Messaging → Try it out → Send a WhatsApp message**
2. Scroll to **Sandbox settings**
3. In the field **"When a message comes in"**, paste:
   ```
   https://your-app.up.railway.app/webhook
   ```
4. Set the method to **HTTP POST**
5. Click **Save**

You're live! 🎉

---

## Using the bot

### Send a text post
Copy a LinkedIn post that contains an email address and paste it into the WhatsApp chat:

```
📌 We're hiring a Senior Data Engineer at Acme Corp!
If interested, send your resume to careers@acmecorp.com
- 5+ yrs Spark/Python experience preferred
- Sarah Johnson, Talent Acquisition
```

### Send a screenshot
Take a screenshot of the LinkedIn post and send it as an image in the chat.

### Workflow
```
You:  [paste LinkedIn post]
Bot:  🔍 Reading your post...
Bot:  📋 Job Found!
      🏢 Acme Corp
      💼 Senior Data Engineer
      👤 HR: Sarah Johnson
      📧 To: careers@acmecorp.com

      Subject: Senior Data Engineer Application – Ravi Sharma
      
      Dear Sarah, ...
      
      Reply SEND | CANCEL | EDIT

You:  SEND
Bot:  ✅ Email sent to careers@acmecorp.com!
```

---

## Commands

| Command  | What it does                              |
|----------|-------------------------------------------|
| `SEND`   | Sends the drafted email to the HR         |
| `CANCEL` | Discards the current draft                |
| `EDIT`   | Asks Claude to regenerate the email       |
| `HELP`   | Shows command list                        |

---

## Tips

- **Best results with text:** Copy-paste the full post text including any pinned comments — the email is often in comments rather than the post body.
- **Screenshot fallback:** Works well when you can't copy text (e.g. mobile LinkedIn).
- **Profile matters:** The more detail you put in `user_profile.json`, the better the emails.
- **No email in post?** The bot will tell you. Some HRs only accept DMs — you can still use the bot by pasting the post and adding the email manually.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Send failed" after SEND | Double-check `GMAIL_APP_PASSWORD` — it must be the App Password, not your Gmail login password |
| Bot doesn't respond | Check Railway logs (`railway logs`) and verify the webhook URL in Twilio is correct |
| "Couldn't parse" error | Try sending the post as text instead of a screenshot |
| Twilio sandbox expired | Re-join the sandbox by sending the join code to the Twilio number again |

---

## Local development (optional)

```bash
pip install -r requirements.txt
cp .env.example .env    # fill in your values
python app.py
```

Expose your local port with [ngrok](https://ngrok.com):
```bash
ngrok http 5000
```
Use the ngrok HTTPS URL as your Twilio webhook.
