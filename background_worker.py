import os
import time
import logging
from fastapi import FastAPI, Request
from fastapi.responses import Response, RedirectResponse
import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler
import gspread
from dotenv import load_dotenv

import email_reader
from email_sender import send_email

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("background_worker")

app = FastAPI(title="Email Outreach Worker")

# Google Sheets Auth
def get_gspread_client():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if creds_json:
        try:
            import json
            from google.oauth2.service_account import Credentials
            creds_dict = json.loads(creds_json)
            creds = Credentials.from_service_account_info(creds_dict, scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ])
            return gspread.authorize(creds)
        except Exception as e:
            logger.error(f"Failed to load credentials from GOOGLE_CREDENTIALS_JSON: {e}")
            return None

    creds_file = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_file or not os.path.exists(creds_file):
        logger.error("GOOGLE_APPLICATION_CREDENTIALS not found!")
        return None
    try:
        return gspread.service_account(filename=creds_file)
    except Exception as e:
        logger.error(f"Failed to connect to Google Sheets: {e}")
        return None

gc = get_gspread_client()
sheet_url_or_id = os.environ.get("GOOGLE_SHEET_URL_OR_ID", "")

# 1x1 transparent GIF pixel
TRANSPARENT_PIXEL = b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'

def update_sheet_status_by_thread(thread_id: str, new_status: str):
    """Finds the row with the given thread_id and updates its status."""
    gc_local = get_gspread_client()
    sheet_url = os.environ.get("GOOGLE_SHEET_URL_OR_ID", "")
    if not gc_local or not sheet_url:
        return
    try:
        import re
        match = re.search(r'/d/([a-zA-Z0-9-_]+)', sheet_url)
        key = match.group(1) if match else sheet_url
        sh = gc_local.open_by_key(key)
            
        for ws in sh.worksheets():
            try:
                all_values = ws.get_all_values()
            except:
                continue
                
            if not all_values or len(all_values) < 2:
                continue
                
            headers = [h.lower().strip() for h in all_values[0]]
            status_col = -1
            thread_col = -1
            
            for i, h in enumerate(headers):
                if 'status' in h and 'email' not in h:
                    status_col = i
                elif 'thread id' in h:
                    thread_col = i
                    
            if status_col == -1 or thread_col == -1:
                continue
                
            for i, row in enumerate(all_values[1:]):
                if len(row) > thread_col and row[thread_col] == thread_id:
                    # Update status if it's not already Replied (don't downgrade)
                    current_status = row[status_col] if len(row) > status_col else ""
                    if current_status.lower() != "replied":
                        from gspread.utils import rowcol_to_a1
                        cell = rowcol_to_a1(i + 2, status_col + 1)
                        ws.update_acell(cell, new_status)
                        logger.info(f"Updated thread {thread_id} to {new_status}")
                        return
    except Exception as e:
        logger.error(f"Failed to update sheet for thread {thread_id}: {e}")

@app.get("/track/open")
def track_open(msg_id: str):
    """Webhook for tracking pixel opens."""
    if msg_id:
        logger.info(f"Email opened: {msg_id}")
        update_sheet_status_by_thread(msg_id, "Opened")
    return Response(content=TRANSPARENT_PIXEL, media_type="image/gif")

@app.get("/track/click")
def track_click(url: str, msg_id: str = ""):
    """Webhook for tracking link clicks."""
    if msg_id:
        logger.info(f"Link clicked in email {msg_id}: {url}")
        update_sheet_status_by_thread(msg_id, "Clicked")
    
    if not url.startswith("http"):
        url = "http://" + url
    return RedirectResponse(url=url)


# ---------------------------------------------------------
# Background Jobs
# ---------------------------------------------------------

def job_check_replies():
    logger.info("Running scheduled IMAP reply check...")
    gc_local = get_gspread_client()
    sheet_url = os.environ.get("GOOGLE_SHEET_URL_OR_ID", "")
    if gc_local and sheet_url:
        email_reader.check_for_replies(gc_local, sheet_url)

def job_drip_send():
    """Sends a small batch of approved emails."""
    logger.info("Running scheduled Drip Send job...")
    
    gc_local = get_gspread_client()
    sheet_url = os.environ.get("GOOGLE_SHEET_URL_OR_ID", "")
    
    if not gc_local or not sheet_url:
        logger.error(f"Missing gc ({bool(gc_local)}) or sheet_url_or_id ({sheet_url})")
        return
        
    try:
        import re
        logger.info(f"Opening sheet with URL/ID: {sheet_url}")
        match = re.search(r'/d/([a-zA-Z0-9-_]+)', sheet_url)
        key = match.group(1) if match else sheet_url
        sh = gc_local.open_by_key(key)
        logger.info(f"Successfully opened sheet: {sh.title}")
            
        def get_setting(sh, key, default):
            try:
                ws = sh.worksheet("Settings")
                cell = ws.find(key, in_column=1)
                if cell:
                    return ws.cell(cell.row, 2).value
                return default
            except:
                return default
                
        def set_setting(sh, key, value):
            try:
                ws = sh.worksheet("Settings")
                cell = ws.find(key, in_column=1)
                if cell:
                    ws.update_cell(cell.row, 2, str(value))
                else:
                    ws.append_row([key, str(value)])
            except gspread.WorksheetNotFound:
                ws = sh.add_worksheet(title="Settings", rows="50", cols="3")
                ws.append_row(["Key", "Value"])
                ws.append_row([key, str(value)])
                
        # Read independent provider delays (default to 600s = 10 mins if not set)
        provider_delays = {
            "Gmail": int(get_setting(sh, "DELAY_Gmail", 600)),
            "Zoho": int(get_setting(sh, "DELAY_Zoho", 600)),
            "Hostinger": int(get_setting(sh, "DELAY_Hostinger", 600)),
        }
        
        current_time = time.time()
        
        from datetime import datetime
        
        # We will track which providers we have already sent an email for in this tick
        providers_sent_this_tick = set()
        
        for ws in sh.worksheets():
            try:
                all_values = ws.get_all_values()
            except:
                continue
                
            if not all_values or len(all_values) < 2:
                continue
                
            headers = all_values[0]
            headers_lower = [h.lower().strip() for h in headers]
            
            def find_col(possible_names):
                for i, h in enumerate(headers_lower):
                    for name in possible_names:
                        if name == 'status' and 'email' in h: continue
                        if name in h: return i
                return -1
                
            status_idx = find_col(['outreach status', 'status'])
            email_idx = find_col(['email', 'contact'])
            subject_idx = find_col(['draft subject', 'subject'])
            body_idx = find_col(['draft body', 'body'])
            thread_idx = find_col(['thread id'])
            last_contacted_idx = find_col(['last contacted date', 'last contacted', 'contact date'])
            orig_body_idx = find_col(['original email body'])
            
            if -1 in [status_idx, email_idx, subject_idx, body_idx]:
                continue
                
            for i, row in enumerate(all_values[1:]):
                row_idx = i + 2
                while len(row) < len(headers):
                    row.append("")
                    
                status = row[status_idx].strip()
                if status.startswith("Queued - "):
                    provider = status.split("Queued - ")[1].strip()
                    
                    if provider not in provider_delays:
                        provider = "Hostinger"
                        
                    # Check if this provider has already sent an email in this run (max 1 per run per provider)
                    if provider in providers_sent_this_tick:
                        continue
                        
                    setting_key = f"LAST_SENT_{provider.upper().replace(' ', '_')}"
                    last_sent_timestamp = float(get_setting(sh, setting_key, 0))
                    
                    send_delay_sec = provider_delays.get(provider, 600)
                    if current_time - last_sent_timestamp < send_delay_sec:
                        continue # Skip this lead, provider is in cooldown
                        
                    to_email = row[email_idx]
                    subject = row[subject_idx]
                    body = row[body_idx]
                    thread_id = row[thread_idx] if thread_idx != -1 and len(row) > thread_idx else ""
                    
                    if to_email and subject and body:
                        # tracking_url setup will be handled in email_sender if we pass it, 
                        # but we can also just let email_sender pull it from env.
                        success, result = send_email(to_email, subject, body, thread_id=thread_id, provider=provider)
                        
                        from gspread.utils import rowcol_to_a1
                        if success:
                            msg_id = result
                            ws.update_acell(rowcol_to_a1(row_idx, status_idx + 1), "Sent")
                            if thread_idx != -1 and msg_id:
                                ws.update_acell(rowcol_to_a1(row_idx, thread_idx + 1), msg_id)
                            if orig_body_idx != -1:
                                ws.update_acell(rowcol_to_a1(row_idx, orig_body_idx + 1), body)
                            if last_contacted_idx != -1:
                                ws.update_acell(rowcol_to_a1(row_idx, last_contacted_idx + 1), datetime.now().strftime("%Y-%m-%d"))
                            
                            providers_sent_this_tick.add(provider)
                            set_setting(sh, setting_key, time.time())
                        else:
                            error_msg = result
                            ws.update_acell(rowcol_to_a1(row_idx, status_idx + 1), f"Failed: {error_msg}")
                            # We don't update the timestamp so it can try another email for this provider next tick
                            
    except Exception as e:
        logger.error(f"Error in drip send job: {e}")

# Scheduler setup
scheduler = BackgroundScheduler()
# Check replies every hour
scheduler.add_job(job_check_replies, 'interval', minutes=60)
# Drip send process queue (checks every 1 minute if it's time to send)
scheduler.add_job(job_drip_send, 'interval', minutes=1)

@app.on_event("startup")
def startup_event():
    scheduler.start()
    logger.info("Background scheduler started.")

@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown()
    logger.info("Background scheduler shut down.")

if __name__ == "__main__":
    uvicorn.run("background_worker:app", host="0.0.0.0", port=8000, reload=True)
