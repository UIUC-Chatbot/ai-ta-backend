import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_email(subject, body_text, sender, receipients):
    # Create message content
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = sender

    if len(receipients) == 1:
        message["To"] = receipients[0]
    else:
        message["To"] = ", ".join(receipients)

    # Add plain text part
    part1 = MIMEText(body_text, "plain")
    message.attach(part1)

    # Add additional parts for HTML, attachments, etc. (optional)

    # Connect to SMTP server
    with smtplib.SMTP_SSL(os.getenv('SES_HOST'), os.getenv('SES_PORT')) as server: # type: ignore
        server.login(os.getenv('USERNAME_SMTP'), os.getenv('PASSWORD_SMTP'))    # type: ignore
        server.sendmail(sender, receipients, message.as_string())

    return "Email sent successfully!"