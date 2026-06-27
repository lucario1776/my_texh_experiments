import os
import json
import re
import base64
import logging
import threading
import io
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client as TwilioClient
import google.generativeai as genai
import PIL.Image
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
gemini   = genai.GenerativeModel("gemini-1.5-flash")
twilio   = TwilioClient(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
WA_FROM  = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")

# In-memory session store  {phone_number: {email, subject, body, job_info}}
sessions = {}


# ─────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────

def send_wa(to: str, body: str):
    """Send a WhatsApp message via Twilio REST API."""
    try:
        twilio.messages.create(body=body, from_=WA_FROM, to=to)
    except Exception as e:
        logger.error(f"send_wa failed → {e}")


def load_profile() -> dict:
    try:
        with open("user_profile.json") as f:
            return json.load(f)
    except Exception:
        return {
            "name": "Applicant",
            "current_role": "Data Engineer",
            "years_experience": 3,
            "skills": ["Python", "SQL", "Apache Spark", "Airflow", "dbt", "AWS"],
            "brief_summary": "Experienced data engineer specialising in building scalable pipelines.",
            "linkedin": "",
            "portfolio": "",
        }


def clean_json(text: str) -> dict:
    text = re.sub(r"```(?:json)?\s*|\s*```", "", text).strip()
    return json.loads(text)


# ─────────────────────────────────────────────────
# Gemini calls
# ─────────────────────────────────────────────────

def extract_job_info(text: str = None, image_url: str = None) -> dict:
    """Ask Gemini to pull email, HR name, company, and role out of a LinkedIn post."""
    instruction = (
        "Extract the following from this LinkedIn job post. "
        'Return ONLY valid JSON — no explanation, no markdown:\n'
        '{"email": "...", "hr_name": "...", "company": "...", "job_title": "..."}\n'
        "Use null for any field that is not found."
    )

    if image_url:
        img = requests.get(
            image_url,
            auth=HTTPBasicAuth(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN")),
            timeout=20,
        )
        img.raise_for_status()
        pil_image = PIL.Image.open(io.BytesIO(img.content))
        resp = gemini.generate_content([pil_image, instruction])
    else:
        resp = gemini.generate_content(f"LinkedIn post:\n\n{text[:3500]}\n\n{instruction}")

    return clean_json(resp.text)


def generate_email(job_info: dict, profile: dict) -> dict:
    """Generate a personalised job-application email via Gemini."""
    prompt = f"""Write a professional job application email. Return ONLY JSON — no markdown:
{{"subject": "...", "body": "..."}}

Role      : {job_info.get("job_title") or "Data Engineer"} at {job_info.get("company") or "the company"}
HR name   : {job_info.get("hr_name") or "Hiring Manager"}
Applicant : {profile.get("name")}, {profile.get("years_experience")} yrs as {profile.get("current_role")}
Skills    : {", ".join(profile.get("skills", []))}
Summary   : {profile.get("brief_summary", "")}
LinkedIn  : {profile.get("linkedin", "")}
Portfolio : {profile.get("portfolio", "")}

Tone: professional, warm, concise — under 180 words. No clichés. End with a clear call to action."""

    resp = gemini.generate_content(prompt)
    return clean_json(resp.text)


# ─────────────────────────────────────────────────
# Email sending  (Gmail or Outlook — set EMAIL_PROVIDER in .env)
# ─────────────────────────────────────────────────

SMTP_PROVIDERS = {
    "gmail": {
        "host":     "smtp.gmail.com",
        "port":     465,
        "use_ssl":  True,
        "address":  "GMAIL_ADDRESS",
        "password": "GMAIL_APP_PASSWORD",
    },
    "outlook": {
        "host":     "smtp.office365.com",
        "port":     587,
        "use_ssl":  False,
        "address":  "OUTLOOK_ADDRESS",
        "password": "OUTLOOK_PASSWORD",
    },
}

def send_email(to: str, subject: str, body: str, profile: dict):
    provider = os.getenv("EMAIL_PROVIDER", "gmail").lower()
    cfg = SMTP_PROVIDERS.get(provider)
    if not cfg:
        raise ValueError(f"Unknown EMAIL_PROVIDER '{provider}'. Choose 'gmail' or 'outlook'.")

    from_addr = os.getenv(cfg["address"])
    password  = os.getenv(cfg["password"])

    if not from_addr or not password:
        raise ValueError(
            f"Missing credentials for {provider}. "
            f"Set {cfg['address']} and {cfg['password']} in your .env"
        )

    msg = MIMEMultipart()
    msg["From"]    = f"{profile.get('name', '')} <{from_addr}>"
    msg["To"]      = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    if cfg["use_ssl"]:
        with smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=30) as s:
            s.login(from_addr, password)
            s.sendmail(from_addr, to, msg.as_string())
    else:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=30) as s:
            s.starttls()
            s.login(from_addr, password)
            s.sendmail(from_addr, to, msg.as_string())


# ─────────────────────────────────────────────────
# Formatting
# ─────────────────────────────────────────────────

def preview(data: dict) -> str:
    j = data.get("job_info", {})
    return (
        f"📋 *Job Found!*\n"
        f"🏢 {j.get('company') or 'Unknown company'}\n"
        f"💼 {j.get('job_title') or 'Unknown role'}\n"
        f"👤 HR: {j.get('hr_name') or 'Unknown'}\n"
        f"📧 To: {data['email']}\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"✉️ *Subject:* {data['subject']}\n\n"
        f"{data['body']}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"Reply *SEND* to send  |  *CANCEL* to discard  |  *EDIT* to regenerate"
    )


# ─────────────────────────────────────────────────
# Background job processor
# ─────────────────────────────────────────────────

def process_post(from_num: str, text: str, image_url: str):
    try:
        profile  = load_profile()
        job_info = extract_job_info(text=text or None, image_url=image_url or None)

        if not job_info.get("email"):
            send_wa(from_num,
                "⚠️ No email address found in this post.\n\n"
                "The post needs to include something like:\n"
                "\"Send your CV to name@company.com\"\n\n"
                "Try copying the full post text including any comments.")
            return

        ec = generate_email(job_info, profile)
        sessions[from_num] = {
            "email":    job_info["email"],
            "subject":  ec["subject"],
            "body":     ec["body"],
            "job_info": job_info,
        }
        send_wa(from_num, preview(sessions[from_num]))

    except json.JSONDecodeError:
        send_wa(from_num,
            "⚠️ Couldn't parse the post. Try sending the text of the post directly "
            "(copy-paste) instead of a screenshot.")
    except Exception as e:
        logger.error(f"process_post error: {e}", exc_info=True)
        send_wa(from_num, f"❌ Something went wrong: {str(e)[:120]}\n\nTry again or reply HELP.")


# ─────────────────────────────────────────────────
# Webhook
# ─────────────────────────────────────────────────

HELP_TEXT = (
    "🤖 *LinkedIn Job Bot*\n\n"
    "1️⃣  Copy a LinkedIn post (with an email) and send it here\n"
    "    — or send a screenshot of the post\n"
    "2️⃣  I'll read the post and draft an application email\n"
    "3️⃣  Review the draft, then reply *SEND*\n\n"
    "*Commands*\n"
    "SEND   — Send the email ✉️\n"
    "CANCEL — Discard current draft ❌\n"
    "EDIT   — Regenerate the email 🔄\n"
    "HELP   — Show this message ℹ️"
)


@app.route("/webhook", methods=["POST"])
def webhook():
    body     = request.form.get("Body", "").strip()
    media    = request.form.get("MediaUrl0")
    from_num = request.form.get("From")
    cmd      = body.upper()

    resp  = MessagingResponse()
    reply = resp.message()

    # ── SEND ────────────────────────────────────────
    if cmd == "SEND":
        if from_num not in sessions:
            reply.body("⚠️ No pending email. Send me a LinkedIn post first!")
            return str(resp)
        s = sessions[from_num]
        try:
            send_email(s["email"], s["subject"], s["body"], load_profile())
            reply.body(f"✅ Email sent to {s['email']}!")
            del sessions[from_num]
        except Exception as e:
            reply.body(f"❌ Send failed: {str(e)[:200]}\n\nCheck your email credentials in .env (EMAIL_PROVIDER, address & password).")
        return str(resp)

    # ── CANCEL ──────────────────────────────────────
    if cmd == "CANCEL":
        sessions.pop(from_num, None)
        reply.body("❌ Cancelled. Send me a new post whenever you're ready!")
        return str(resp)

    # ── EDIT ────────────────────────────────────────
    if cmd == "EDIT":
        if from_num not in sessions:
            reply.body("⚠️ No pending email to edit. Send me a LinkedIn post first!")
            return str(resp)
        try:
            ec = generate_email(sessions[from_num]["job_info"], load_profile())
            sessions[from_num].update({"subject": ec["subject"], "body": ec["body"]})
            reply.body("🔄 Regenerated!\n\n" + preview(sessions[from_num]))
        except Exception as e:
            reply.body(f"❌ Regeneration failed: {e}")
        return str(resp)

    # ── HELP ────────────────────────────────────────
    if cmd == "HELP":
        reply.body(HELP_TEXT)
        return str(resp)

    # ── New post: acknowledge immediately, process in background ──
    if not body and not media:
        reply.body("👋 Send me a LinkedIn job post (text or screenshot) and I'll draft an email!\n\nReply HELP for instructions.")
        return str(resp)

    reply.body("🔍 Reading your post...")
    threading.Thread(target=process_post, args=(from_num, body, media), daemon=True).start()
    return str(resp)


@app.route("/health")
def health():
    return {"status": "ok", "active_sessions": len(sessions)}, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
