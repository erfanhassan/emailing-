import os
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

load_dotenv()

smtp_server = "smtp.hostinger.com"
smtp_port = 465

sender_email = os.environ.get("HOSTINGER_EMAIL")
sender_password = os.environ.get("HOSTINGER_PASSWORD")
to_email = "test@example.com"

print(f"Testing SMTP login for {sender_email}")

msg = MIMEMultipart()
msg['From'] = sender_email
msg['To'] = to_email
msg['Subject'] = "Test Email"
msg.attach(MIMEText("Test body", 'plain'))

try:
    with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
        server.set_debuglevel(1)
        server.login(sender_email, sender_password)
        print("LOGIN SUCCESS")
        # Don't actually send to a fake address to avoid bouncing, just login is enough.
        # server.send_message(msg)
except Exception as e:
    import traceback
    traceback.print_exc()
