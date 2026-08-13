import os
from dotenv import load_dotenv
import logging

load_dotenv()

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# We need to import after loading dotenv if it was not already loaded, but email_sender also uses os.environ.
from email_sender import send_email

logging.basicConfig(level=logging.INFO)

to_email = "E.H.ifti@gmail.com"
subject = "Test Email from Outreach App"
body = "This is a test email to verify SMTP configuration for the Outreach dashboard."

providers = [
    ("Hostinger", os.environ.get("HOSTINGER_EMAIL"), os.environ.get("HOSTINGER_PASSWORD")),
    ("Gmail", os.environ.get("GMAIL_EMAIL"), os.environ.get("GMAIL_PASSWORD")),
    ("Zoho Mail", os.environ.get("ZOHO_EMAIL"), os.environ.get("ZOHO_PASSWORD"))
]

for provider, email, password in providers:
    print(f"\n--- Testing Provider: {provider} ({email}) ---")
    if not email or not password:
        print(f"Skipping {provider} - Missing credentials in .env")
        continue
        
    try:
        success, msg_id = send_email(
            to_email=to_email,
            subject=f"{subject} via {provider}",
            body=body,
            provider=provider,
            sender_email=email,
            sender_password=password
        )
        
        if success:
            print(f"SUCCESS: Email sent via {provider}. Message ID: {msg_id}")
        else:
            print(f"FAILED: Email failed to send via {provider}.")
    except Exception as e:
        print(f"ERROR: {e}")
