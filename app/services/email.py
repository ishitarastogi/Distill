"""SMTP helper for digest delivery."""
"""
Raw SMTP send via Gmail app password.

Needs two environment variables:
  MY_EMAIL=youraddress@gmail.com
  EMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx   (from Google Account > Security
                                              > 2-Step Verification > App passwords)
"""

from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import smtplib

load_dotenv()


def send_email(subject: str, html_body: str, to_address: str = None) -> bool:
    my_email = os.getenv("MY_EMAIL")
    app_password = os.getenv("EMAIL_APP_PASSWORD")

    if not my_email or not app_password:
        raise ValueError(
            "MY_EMAIL and EMAIL_APP_PASSWORD must be set in .env"
        )

    to_address = to_address or my_email

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = my_email
    message["To"] = to_address
    message.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(my_email, app_password)
            server.sendmail(my_email, to_address, message.as_string())
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False


if __name__ == "__main__":
    success = send_email(
        subject="Distill test email",
        html_body="<p>Test from Python — if you got this, SMTP is working.</p>",
    )
    print("Sent" if success else "Failed")
