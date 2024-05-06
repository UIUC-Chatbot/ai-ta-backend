import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import supabase


def send_html_email(subject: str, html_text: str, sender: str, receipients: list, bcc_receipients: list):
  """
    Send an email using the AWS SES service
    :param subject: The subject of the email
    :param body_text: The body of the email
    :param sender: The email address of the sender
    :param receipients: A list of email addresses to send the email to
    :param bcc_receipients: A list of email addresses to send the email to as BCC
    :return: A string indicating the result of the email send operation
    """
  
  supabase_client = supabase.create_client(  # type: ignore
        supabase_url=os.environ['SUPABASE_URL'], supabase_key=os.environ['SUPABASE_API_KEY'])
  
  # Get the list of unsubscribed emails
  unsubscribe_list = supabase_client.table(table_name='email-newsletter').select("email").eq("unsubscribed-from-newsletter", "TRUE").execute()

  # Remove any receipients that are in the unsubscribe list
  new_receipients = [r for r in receipients if r not in unsubscribe_list]

  # Create message content
  message = MIMEMultipart("alternative")
  message["Subject"] = subject
  message["From"] = sender
  message["To"] = ", ".join(new_receipients)

  if len(bcc_receipients) > 0:
    message["Bcc"] = ", ".join(bcc_receipients)

  # Add plain text part
  part1 = MIMEText(html_text, "html")
  message.attach(part1)

  # Add additional parts for HTML, attachments, etc. (optional)

  # Connect to SMTP server
  with smtplib.SMTP_SSL(os.getenv('SES_HOST'), os.getenv('SES_PORT')) as server:  # type: ignore
    server.login(os.getenv('USERNAME_SMTP'), os.getenv('PASSWORD_SMTP'))  # type: ignore
    server.sendmail(sender, receipients + bcc_receipients, message.as_string())

  return "Email sent successfully!"
