import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

def send_email(to_email, subject, html_body, pdf_path=None):
    smtp_host = "smtp.gmail.com"   # hardcoded correct Gmail SMTP host
    try:
        smtp_port = int(os.environ.get("SMTP_PORT", 587))
    except (ValueError, TypeError):
        smtp_port = 587

    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")
    email_from = os.environ.get("EMAIL_FROM") or smtp_user

    if not smtp_user or not smtp_pass:
        print("Mailing Error: SMTP_USER or SMTP_PASS environment variables are missing.")
        return {"status": "error", "message": "Email server credentials missing"}

    try:
        msg = MIMEMultipart()
        msg["From"]    = email_from
        msg["To"]      = to_email
        msg["Subject"] = subject

        msg.attach(MIMEText(html_body, "html"))

        # Attach PDF if path provided
        if pdf_path:
            full_path = pdf_path if os.path.isabs(pdf_path) else os.path.join(os.getcwd(), pdf_path)
            if os.path.exists(full_path):
                with open(full_path, "rb") as f:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(f.read())
                    encoders.encode_base64(part)
                    filename = os.path.basename(full_path)
                    part.add_header("Content-Disposition", f"attachment; filename={filename}")
                    msg.attach(part)
            else:
                print(f"PDF not found at path: {full_path}")

        server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(smtp_user, smtp_pass)
        server.sendmail(email_from, to_email, msg.as_string())
        server.quit()

        print(f"Email delivered successfully to {to_email}")
        return {"status": "sent", "to": to_email, "subject": subject}

    except Exception as e:
        print(f"SMTP Error: {str(e)}")
        return {"status": "error", "message": f"SMTP failure: {str(e)}"}
