import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import supabase
import requests

def get_all_users():

  done = False
  all_users = []
  offset = 0
  limit = 100
  headers = {'Authorization': f'Bearer {os.environ["CLERK_BEARER_TOKEN"]}'}
  while not done: 
    users = requests.get(f"https://api.clerk.com/v1/users?limit={limit}&offset={offset}&order_by=-created_at", headers=headers)
    print(users.json())
    all_users.extend(users.json())
    if len(users.json()) == 0: 
      done = True
    offset = offset + limit
  return all_users


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
  
  # Get list of users
  users = get_all_users()
  emails = [user['email_addresses'][0]['email_address'] for user in users]
  
  # Get the list of unsubscribed emails
  unsubscribed = supabase_client.table(table_name='email-newsletter').select("email").eq("unsubscribed-from-newsletter", "TRUE").execute()
  unsubscribe_list = [row['email'] for row in unsubscribed.data]

  # Remove any receipients that are in the unsubscribe list
  new_receipients = [r for r in emails if r not in unsubscribe_list]

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
