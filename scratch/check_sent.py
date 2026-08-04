import os
import imaplib
import email
from email.header import decode_header
from dotenv import load_dotenv

load_dotenv(override=True)

sender_email = os.environ.get("HOSTINGER_EMAIL")
sender_password = os.environ.get("HOSTINGER_PASSWORD")
imap_server = "imap.hostinger.com"

try:
    with imaplib.IMAP4_SSL(imap_server, 993) as imap:
        imap.login(sender_email, sender_password)
        
        # Check INBOX.Sent
        sent_folder = "INBOX.Sent"
        status, messages = imap.select(f'"{sent_folder}"')
        if status == 'OK':
            total = int(messages[0])
            print(f"Total messages in {sent_folder}: {total}")
            
            # Print details of the sent messages
            for i in range(total, 0, -1):
                status, msg_data = imap.fetch(str(i), '(RFC822)')
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        subject, encoding = decode_header(msg["Subject"])[0]
                        if isinstance(subject, bytes):
                            subject = subject.decode(encoding or "utf-8", errors="ignore")
                        to_, encoding = decode_header(msg["To"])[0]
                        if isinstance(to_, bytes):
                            to_ = to_.decode(encoding or "utf-8", errors="ignore")
                        date_ = msg.get("Date")
                        print(f"  Index: {i}, Date: {date_}, To: {to_}, Subject: {subject}")
        else:
            print(f"Could not select {sent_folder}")
except Exception as e:
    print(f"Error checking Sent folder: {e}")
