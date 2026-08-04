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
    creds_file = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_file or not os.path.exists(creds_file):
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
    if not gc or not sheet_url_or_id:
        return
    try:
        if "spreadsheets.google.com" in sheet_url_or_id:
            sh = gc.open_by_url(sheet_url_or_id)
        else:
            sh = gc.open_by_key(sheet_url_or_id)
            
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
    if gc and sheet_url_or_id:
        email_reader.check_for_replies(gc, sheet_url_or_id)

def job_drip_send():
    """Sends a small batch of approved emails."""
    logger.info("Running scheduled Drip Send job...")
    if not gc or not sheet_url_or_id:
        return
        
    try:
        if "spreadsheets.google.com" in sheet_url_or_id:
            sh = gc.open_by_url(sheet_url_or_id)
        else:
            sh = gc.open_by_key(sheet_url_or_id)
            
        # Send max 2 emails per run to drip slowly
        max_to_send = 2
        sent_count = 0
        
        from datetime import datetime
        
        for ws in sh.worksheets():
            if sent_count >= max_to_send:
                break
                
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
                if sent_count >= max_to_send:
                    break
                    
                row_idx = i + 2
                while len(row) < len(headers):
                    row.append("")
                    
                status = row[status_idx]
                if status.strip().lower() == "approved":
                    to_email = row[email_idx]
                    subject = row[subject_idx]
                    body = row[body_idx]
                    thread_id = row[thread_idx] if thread_idx != -1 and len(row) > thread_idx else ""
                    
                    if to_email and subject and body:
                        # tracking_url setup will be handled in email_sender if we pass it, 
                        # but we can also just let email_sender pull it from env.
                        success, msg_id = send_email(to_email, subject, body, thread_id=thread_id)
                        
                        from gspread.utils import rowcol_to_a1
                        if success:
                            ws.update_acell(rowcol_to_a1(row_idx, status_idx + 1), "Sent")
                            if thread_idx != -1 and msg_id:
                                ws.update_acell(rowcol_to_a1(row_idx, thread_idx + 1), msg_id)
                            if orig_body_idx != -1:
                                ws.update_acell(rowcol_to_a1(row_idx, orig_body_idx + 1), body)
                            if last_contacted_idx != -1:
                                ws.update_acell(rowcol_to_a1(row_idx, last_contacted_idx + 1), datetime.now().strftime("%Y-%m-%d"))
                            
                            sent_count += 1
                            time.sleep(2)
                            
    except Exception as e:
        logger.error(f"Error in drip send job: {e}")

# Scheduler setup
scheduler = BackgroundScheduler()
# Check replies every hour
scheduler.add_job(job_check_replies, 'interval', minutes=60)
# Drip send 2 emails every 15 minutes
scheduler.add_job(job_drip_send, 'interval', minutes=15)

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
