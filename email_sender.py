import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

import email.utils

logger = logging.getLogger(__name__)

def send_email(to_email: str, subject: str, body: str, thread_id: str = None, provider: str = None, sender_email: str = None, sender_password: str = None) -> tuple[bool, str]:
    """
    Sends an email using the configured SMTP provider.
    Returns (True, message_id) if successful, (False, "") otherwise.
    """
    if not to_email or not to_email.strip():
        logger.error("Recipient email is empty.")
        return False, ""

    provider = provider or os.environ.get("SMTP_PROVIDER", "Hostinger")
    sender_email = sender_email or os.environ.get("SMTP_EMAIL", os.environ.get("HOSTINGER_EMAIL"))
    sender_password = sender_password or os.environ.get("SMTP_PASSWORD", os.environ.get("HOSTINGER_PASSWORD"))

    if not sender_email or not sender_password:
        logger.error("Email credentials not found.")
        return False, ""
        
    if provider == "Gmail":
        smtp_server = "smtp.gmail.com"
        smtp_port = 465
        imap_server = "imap.gmail.com"
        imap_folder = '"[Gmail]/Sent Mail"'
    elif provider == "Zoho Mail":
        smtp_server = "smtp.zoho.com"
        smtp_port = 465
        imap_server = "imap.zoho.com"
        imap_folder = "Sent"
    else:
        smtp_server = "smtp.hostinger.com"
        smtp_port = 465
        imap_server = "imap.hostinger.com"
        imap_folder = "INBOX.Sent"

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = to_email
    msg['Subject'] = subject
    
    domain = sender_email.split('@')[-1] if '@' in sender_email else "weautomate.sonictch.com"
    message_id = email.utils.make_msgid(domain=domain)
    msg['Message-ID'] = message_id
    msg['Date'] = email.utils.formatdate(localtime=True)
    
    if thread_id:
        msg['In-Reply-To'] = thread_id
        msg['References'] = thread_id
    
    body_lower = body.lower()
    is_html = "<br" in body_lower or "<p" in body_lower or "<html" in body_lower or "<body" in body_lower or "<a " in body_lower
    
    if not is_html:
        import re
        body = re.sub(r'(https?://[^\s<]+)', r'<a href="\1">\1</a>', body)
        body = body.replace("\n", "<br>")
        
    tracking_url = os.environ.get("TRACKING_URL", "").rstrip("/")
    if tracking_url:
        import re
        from urllib.parse import quote
        
        # 1. Rewrite hrefs for click tracking
        def rewrite_link(match):
            original_url = match.group(1)
            if "track/click" in original_url or original_url.startswith("mailto:"):
                return match.group(0)
            encoded_url = quote(original_url, safe='')
            return f'href="{tracking_url}/track/click?url={encoded_url}&msg_id={message_id}"'
            
        body = re.sub(r'href="(.*?)"', rewrite_link, body)
        
        # 2. Inject open tracking pixel
        pixel_tag = f'<img src="{tracking_url}/track/open?msg_id={message_id}" width="1" height="1" alt="" style="display:none;" />'
        if "</body>" in body.lower():
            body = re.sub(r'(?i)</body>', f'{pixel_tag}</body>', body)
        else:
            body += f'<br>{pixel_tag}'

    msg.attach(MIMEText(body, 'html'))
    
    try:
        # Hostinger uses port 465 for SMTP with SSL
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(sender_email, sender_password)
            server.send_message(msg)
            
        # Append to Sent folder via IMAP
        try:
            import imaplib
            import time
            with imaplib.IMAP4_SSL(imap_server, 993) as imap:
                imap.login(sender_email, sender_password)
                imap.append(imap_folder, None, imaplib.Time2Internaldate(time.time()), msg.as_bytes())
        except Exception as imap_e:
            logger.warning(f"Failed to save email to Sent folder (IMAP): {imap_e}")
            
        return True, message_id
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP Authentication Error for {sender_email}: {e}")
        return False, ""
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False, ""
