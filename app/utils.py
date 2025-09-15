import os
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

ONBOARDING_SECRET = os.getenv("ONBOARDING_SECRET", "dev-secret")
EMAIL_FROM = os.getenv("EMAIL_FROM", "no-reply@claimsafer.com")
SMTP_HOST = os.getenv("SMTP_HOST", "localhost")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")

def normalize_email(email: str) -> str:
    """Normalize email by stripping spaces and lowercasing."""
    return email.strip().lower()

def sign_onboarding_token(email: str) -> str:
    serializer = URLSafeTimedSerializer(ONBOARDING_SECRET)
    return serializer.dumps(email, salt="onboarding")

def verify_onboarding_token(token: str, max_age_seconds: int = 604800) -> str:
    serializer = URLSafeTimedSerializer(ONBOARDING_SECRET)
    try:
        return serializer.loads(token, salt="onboarding", max_age=max_age_seconds)
    except (BadSignature, SignatureExpired) as e:
        raise

def send_email(to_email: str, subject: str, html: str, text: str = None):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = to_email
    part1 = MIMEText(text or html, "plain")
    part2 = MIMEText(html, "html")
    msg.attach(part1)
    msg.attach(part2)
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        if SMTP_USER:
            server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(EMAIL_FROM, to_email, msg.as_string())
