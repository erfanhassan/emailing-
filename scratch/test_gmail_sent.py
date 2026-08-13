import sys
import os
import logging
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.DEBUG)

from email_sender import send_email

to_email = "ehiftyhassan@gmail.com"  # Send to self or test email
subject = "Test from Python Script for Gmail"
body = "This is a test to see if it appears in the sent folder."

success, msg_id = send_email(to_email, subject, body, provider="Gmail")
print(f"Success: {success}, MsgID: {msg_id}")
