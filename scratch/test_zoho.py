import os
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

load_dotenv()

def test_zoho():
    sender_email = os.environ.get("ZOHO_EMAIL")
    sender_password = os.environ.get("ZOHO_PASSWORD")
    to_email = "E.H.ifti@gmail.com"
    
    print(f"Testing Zoho Mail ({sender_email}) to {to_email}")
    
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = to_email
    msg['Subject'] = "Debug Test from Zoho"
    msg.attach(MIMEText("This is a direct debug test from Zoho.", 'plain'))
    
    try:
        with smtplib.SMTP_SSL("smtp.zoho.com", 465) as server:
            server.set_debuglevel(1)
            server.login(sender_email, sender_password)
            print("Login successful. Sending message...")
            server.send_message(msg)
            print("Message accepted by Zoho SMTP.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    test_zoho()
