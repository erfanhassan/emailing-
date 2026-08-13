import os
import imaplib
import email
from email.header import decode_header
import logging
import gspread
import time

logger = logging.getLogger(__name__)

def connect_imap() -> imaplib.IMAP4_SSL:
    """Connects to the IMAP server of the currently configured SMTP provider."""
    provider = os.environ.get("SMTP_PROVIDER", "Hostinger")

    if provider == "Gmail":
        imap_host = "imap.gmail.com"
        email_key = "GMAIL_EMAIL"
        pass_key = "GMAIL_PASSWORD"
    elif provider == "Zoho Mail":
        imap_host = "imap.zoho.com"
        email_key = "ZOHO_EMAIL"
        pass_key = "ZOHO_PASSWORD"
    else:  # Hostinger default
        imap_host = "imap.hostinger.com"
        email_key = "HOSTINGER_EMAIL"
        pass_key = "HOSTINGER_PASSWORD"

    sender_email = os.environ.get("SMTP_EMAIL") or os.environ.get(email_key)
    sender_password = os.environ.get("SMTP_PASSWORD") or os.environ.get(pass_key)

    if not sender_email or not sender_password:
        logger.error(f"Credentials not found for provider '{provider}' in env.")
        return None

    try:
        imap = imaplib.IMAP4_SSL(imap_host, 993)
        imap.login(sender_email, sender_password)
        logger.info(f"IMAP connected to {imap_host} as {sender_email}")
        return imap
    except Exception as e:
        logger.error(f"Failed to connect to IMAP ({imap_host}): {e}")
        return None


def check_for_replies(gc: gspread.Client, sheet_url_or_id: str, max_emails: int = 50):
    """
    Scans the INBOX for replies and updates the Google Sheet.
    Matches the 'In-Reply-To' or 'References' headers with the 'Thread ID' column in the sheet.
    """
    if not gc or not sheet_url_or_id:
        logger.error("Google Sheets client or URL missing.")
        return
        
    imap = connect_imap()
    if not imap:
        return
        
    try:
        # Open Google
        try:
            import re
            match = re.search(r'/d/([a-zA-Z0-9-_]+)', sheet_url_or_id)
            key = match.group(1) if match else sheet_url_or_id
            sh = gc.open_by_key(key)
        except Exception as e:
            logger.error(f"Failed to open spreadsheet: {e}")
            return
            
        # Iterate over all worksheets
        worksheets = sh.worksheets()
        for ws in worksheets:
            try:
                all_values = ws.get_all_values()
            except Exception:
                continue
                
            if not all_values or len(all_values) < 2:
                continue
                
            headers = [h.lower().strip() for h in all_values[0]]
            
            status_col = -1
            thread_col = -1
            
            # Find necessary columns
            for i, h in enumerate(headers):
                if 'status' in h and 'email' not in h:
                    status_col = i
                elif 'thread id' in h:
                    thread_col = i
                    
            if status_col == -1 or thread_col == -1:
                continue
                
            # Build a map of Thread ID -> Row Index
            thread_to_row = {}
            for i, row in enumerate(all_values[1:]):
                if len(row) > thread_col:
                    thread_id = row[thread_col]
                    status = row[status_col] if len(row) > status_col else ""
                    if thread_id and status.lower() != "replied":
                        # i + 2 because row 1 is headers and array is 0-indexed
                        thread_to_row[thread_id] = i + 2
            
            if not thread_to_row:
                continue # No pending threads in this worksheet
                
            # Now fetch recent emails from INBOX
            imap.select("INBOX")
            # Search for ALL emails, or use a date filter if inbox is large. 
            # We'll just fetch the most recent ones.
            status, messages = imap.search(None, "ALL")
            if status != "OK":
                continue
                
            email_ids = messages[0].split()
            recent_ids = email_ids[-max_emails:] # only look at the last N emails to save time
            
            for eid in recent_ids:
                status, msg_data = imap.fetch(eid, "(RFC822.SIZE BODY.PEEK[HEADER.FIELDS (IN-REPLY-TO REFERENCES)])")
                if status != "OK":
                    continue
                
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        headers_str = response_part[1].decode("utf-8", errors="ignore")
                        msg = email.message_from_string(headers_str)
                        
                        in_reply_to = msg.get("In-Reply-To", "").strip()
                        references = msg.get("References", "").strip()
                        
                        # Match with our known threads
                        matched_thread = None
                        for known_thread in thread_to_row.keys():
                            if known_thread in in_reply_to or known_thread in references:
                                matched_thread = known_thread
                                break
                                
                        if matched_thread:
                            row_idx = thread_to_row[matched_thread]
                            # Update sheet status to Replied
                            try:
                                from gspread.utils import rowcol_to_a1
                                cell = rowcol_to_a1(row_idx, status_col + 1)
                                ws.update_acell(cell, "Replied")
                                logger.info(f"Updated row {row_idx} in {ws.title} to Replied based on IMAP match.")
                                # Remove from dict so we don't update multiple times if there are multiple replies
                                del thread_to_row[matched_thread]
                            except Exception as update_err:
                                logger.error(f"Failed to update sheet: {update_err}")
                                
    except Exception as e:
        logger.error(f"Error checking for replies: {e}")
    finally:
        try:
            imap.logout()
        except:
            pass

if __name__ == "__main__":
    # Test block
    logging.basicConfig(level=logging.INFO)
    logger.info("Email reader script loaded.")
